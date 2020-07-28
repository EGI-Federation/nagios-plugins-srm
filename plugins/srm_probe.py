#!/usr/bin/env python
##############################################################################
# DESCRIPTION
##############################################################################

"""
new SRM probe, using gfal2, NAP, and compatible with python3

"""

import sys
import time
import gridutils
import tempfile
import datetime
import filecmp
import gfal2
import nap.core
import shutil
import os

try:
    from urlparse import urlparse
except BaseException:
    from urllib.parse import urlparse


PROBE_VERSION = "v0.0.5"


# ########################################################################### #
app = nap.core.Plugin(description="NAGIOS SRM probe",
                      version=PROBE_VERSION)
app.add_argument("-E", "--endpoint", help="SRM base SURL to test")
app.add_argument("-X", "--x509", help="location of x509 certificate proxy file")
app.add_argument("-VO", "--voname", help="VO name, needed for interaction with BDII", default="ops")
app.add_argument("--srmv",  help="srm version to use", default='2')
app.add_argument("--ldap-url", help="LDAP URL", dest="ldap_url", default="ldap://lcg-bdii.cern.ch:2170")
app.add_argument("--se-timeout",dest="se_timeout", type=int, help="storage operations timeout", default=60)

# Reasonable defaults for timeouts
LCG_GFAL_BDII_TIMEOUT = 10

gfal2.set_verbose(gfal2.verbose_level.normal)

# Service version(s)
svcVers = ['1','2']  
svcVer = '2'
workdir_metric = tempfile.mkdtemp()

# files and patterns
_fileTest = workdir_metric + '/testFile.txt'
_fileTestIn = workdir_metric + '/testFileIn.txt'
_fileSRMPattern = 'testfile-put-%s-%s.txt'  # time, uuid

_voInfoDictionary = {}

# Instantiate gfal2
ctx = gfal2.creat_context()

# GFAL version
gfal2_ver = "gfal2 " + gfal2.get_version()

def parse_args(args, io):
    
    if args.srmv in svcVers:
        svcVer = str(args.srmv)
    else:
        errstr = 'srmv parameter must be one of '+ \
                ', '.join([x for x in svcVers])+'. '+args.srmv+' given'
        io.set_status(nap.CRITICAL,errstr)
        return  1  
    os.environ['LCG_GFAL_INFOSYS'] = args.ldap_url

    if args.x509:
        cred = gfal2.cred_new("X509_CERT",args.x509)
        gfal2.cred_set(ctx,"srm://",cred)
        gfal2.cred_set(ctx,"gsiftp://",cred)
 


def query_bdii(ldap_filter, ldap_attrlist, ldap_url=''):
    'Local wrapper for gridutils.query_bdii()'
    rc, qres = gridutils.query_bdii(ldap_filter, ldap_attrlist,
                                    ldap_url=ldap_url,
                                    ldap_timelimit=LCG_GFAL_BDII_TIMEOUT)

    return rc, qres

def getSURLFromBDII(args,io):
    ldap_f = "(|(&(GlueChunkKey=GlueSEUniqueID=%s)(|(GlueSAAccessControlBaseRule=%s)(GlueSAAccessControlBaseRule=VO:%s)))" \
        + "(&(GlueChunkKey=GlueSEUniqueID=%s)(|(GlueVOInfoAccessControlBaseRule=%s)(GlueVOInfoAccessControlBaseRule=VO:%s)))" \
        + "(&(GlueServiceUniqueID=*://%s*)(GlueServiceVersion=%s.*)(GlueServiceType=srm*)))"
    ldap_filter = ldap_f % (args.hostname, args.voname, args.voname, args.hostname, args.voname, args.voname, args.hostname, svcVer)
    ldap_attrlist = ['GlueServiceEndpoint', 'GlueSAPath', 'GlueVOInfoPath']

    rc, qres = query_bdii(ldap_filter, ldap_attrlist, args.ldap_url)
    if not rc:
        if qres[0] == 0:  # empty set
            io.status = nap.CRITICAL
        else:  # all other problems
            io.status = nap.UNKNOWN
        io.summary = "Error querying the BDII"
        return []

    res = {}
    for k in ldap_attrlist:
        res[k] = []

    for entry in qres:
        for attr in res.keys():
            try:
                for val in entry[1][attr]:
                    if val not in res[attr]:
                        res[attr].append(val)
            except KeyError:
                pass

    # GlueServiceEndpoint is not published
    k = 'GlueServiceEndpoint'
    if not res[k]:
        io.set_status(nap.CRITICAL,
                      "%s is not published for %s in %s" %
                      (k, args.endpoint, args.ldap_url))
        return []
    elif len(res[k]) > 1:
        io.set_status(
            nap.CRITICAL,
            "More than one SRMv" +
            svcVer +
            " " +
            k +
            " is published for " +
            args.endpoint +
            ": " +
            ', '.join(
                res[k]))
        return[]
    else:
        endpoint = res[k][0]

    if res['GlueVOInfoPath']:
        storpaths = res['GlueVOInfoPath']
        
    elif res['GlueSAPath']:
        storpaths = res['GlueSAPath']
        
    else:
        # GlueSAPath or GlueVOInfoPath is not published
        io.set_status(
            nap.CRITICAL, "GlueVOInfoPath or GlueSAPath not published for %s in %s" %
            (res['GlueServiceEndpoint'][0], args.ldap_url))
        return []

    eps = [
        endpoint.replace(
            'httpg',
            'srm',
            1) +
        '?SFN=' +
        sp for sp in storpaths]

    return eps


@app.metric(seq=1, metric_name="GetSURLs", passive=True)
def getSURLs(args, io):
    """
    Use provided endpoint as SURL or use the BDII to retrieve the Storage Area and build the SURLs to test
    """
    if  parse_args(args,io):
        return 
    eps =[]
    if args.endpoint is None:
        eps = getSURLFromBDII(args,io)
    else:
        eps.append(args.endpoint)
    if len(eps) == 0:
        io.summary = 'Fail to retrieve SURLs to test'
        io.status = nap.CRITICAL
        return
    for ep in eps:
        _voInfoDictionary[ep] = {}
    io.summary = 'SURLs successfully retrieved'
    io.status = nap.OK


@app.metric(seq=2, metric_name="VOLsDir", passive=True)
def metricVOLsDir(args, io):
    """
    List content of VO's top level space area(s) in SRM using gfal2.listdir().
    """
   
    # verify previous test succeeded
    results = app.metric_results()
    if (results[0][1] != nap.OK ):
        io.set_status(nap.WARNING, "VOLsDir skipped")
        return

    srms = []
    try:
        for srm in _voInfoDictionary.keys():
            srms.append(srm)
        if not srms:
            io.set_status(nap.WARNING, 'No SRM endpoints found to test')
            return
    except Exception as e:
        io.set_status('UNKNOWN', 'Error reading SRM to test')
        return

    for surl in srms: 
        try:
            ctx.listdir(str(surl))
            io.summary = 'Storage Path[%s] Directory successfully listed' % str(surl)
            io.status = nap.OK
        except gfal2.GError as e:
            er = e.message
            if er:
                # SRM_TOO_MANY_RESULTS is handled as an error in gfal2, we don't want to report it as Critical here
                if "SRM_TOO_MANY_RESULTS" in er:
                    io.summary = '[WARN:%s];' %  str(er)
                    io.status = nap.WARNING
                else:
                    io.status = nap.CRITICAL
                    io.summary = '[Err:%s];' %  str(er)
            else:
                io.status = nap.CRITICAL
                io.summary = 'Error'
        except Exception as e:
            io.set_status(
                nap.CRITICAL, 'problem invoking gfal2 listdir(): %s:%s' %
                (str(e), sys.exc_info()[0]))


@app.metric(seq=3, metric_name="VOPut", passive=True)
def metricVOPut(args, io):
    """Copy a local file to the SRM into space area(s) defined by VO."""

    # verify VOGetSurls test succeeded
    results = app.metric_results()
    if (results[0][1] != nap.OK ):
        io.set_status(nap.WARNING, "VOLsDir skipped")
        return

    if len(_voInfoDictionary.keys()) == 0:
        io.set_status(nap.WARNING, 'No SRM endpoints found to test')
        return

    # multiple 'SAPath's are possible
    dest_files = []
    # generate source file
    try:
        src_file = _fileTest
        fp = open(src_file, "w")
        for s in "1234567890":
            fp.write(s + '\n')
        fp.close()

        fn = _fileSRMPattern % (str(int(time.time())),
                                gridutils.uuidstr())
        for srmendpt in _voInfoDictionary.keys():
            dest_files.append(srmendpt + '/' + fn)
            _voInfoDictionary[srmendpt]['fn'] = fn
        if not dest_files:
            io.set_status(nap.CRITICAL, 'No SRM endpoints found to test')
            return
    except IOError as e:
        io.set_status(nap.CRITICAL, 'Error creating source file')

    for dest_file in dest_files:
        # Set transfer parameters
        params = ctx.transfer_parameters()
        params.create_parent = True
        params.timeout = args.se_timeout
        start_transfer = datetime.datetime.now()

        stMsg = 'File was%s copied to SRM.'

        try:
            ctx.filecopy(params, "file://" + str(src_file), str(dest_file))
            total_transfer = datetime.datetime.now() - start_transfer
            io.summary = stMsg % '' + " Transfer time: " + str(total_transfer)
            io.status = nap.OK
        except gfal2.GError as e:
            io.status = nap.CRITICAL
            er = e.message
            if er:
                io.summary = stMsg % (' NOT') + ' [Err:%s]' % str(er)
            else:
                io.summary = stMsg % ' NOT'
        except Exception as e:
            io.set_status(
                nap.CRITICAL, 'problem invoking gfal2 filecopy(): %s:%s' %
                (str(e), sys.exc_info()[0]))


@app.metric(seq=4, metric_name="VOLs", passive=True)
def metricVOLs(args, io):
    """Stat (previously copied) file(s) on the SRM."""

     # verify previous test succeeded
    results = app.metric_results()
    if ( results[2][1] != nap.OK ):
        io.set_status(nap.WARNING, "VOLs skipped")
        return

    if len(_voInfoDictionary.keys()) == 0:
        io.set_status(nap.WARNING, 'No SRM endpoints found to test')
        return

    srms = []

    for srmendpt in _voInfoDictionary.keys():
        dest_filename = (_voInfoDictionary[srmendpt])['fn']
        dest_file = srmendpt + '/' + dest_filename
        srms.append(dest_file)

    for surl in srms:
        try:
            statp = ctx.stat(str(surl))

            io.summary = 'File successfully listed'
            io.status = nap.OK
        except gfal2.GError as e:
            er = e.message
            io.status = nap.CRITICAL
            if er:
                io.summary = '[Err:%s];' % str(er)
            else:
                io.summary = 'Error'
       
        except Exception as e:
            io.set_status(
                nap.CRITICAL, 'problem invoking gfal2 stat(): %s:%s' %
                (str(e), sys.exc_info()[0]))


@app.metric(seq=5, metric_name="VOGetTurl", passive=True)
def metricVOGetTURLs(ags, io):
    """Get Transport URLs for the file copied to storage"""

    # verify previous test succeeded
    results = app.metric_results()
    if (results[3][1] != nap.OK ):
        io.set_status(nap.WARNING, "VOGetTurl skipped")
        return

    if len(_voInfoDictionary.keys()) == 0:
        io.set_status(nap.WARNING, 'No SRM endpoints found to test')
        return

    for srmendpt in _voInfoDictionary.keys():

        src_filename = (_voInfoDictionary[srmendpt])['fn']
        src_file = srmendpt + '/' + src_filename
        protocol = 'gsiftp'
        try:
            if urlparse(src_file).scheme == 'gsiftp':
                # If protocol is gsiftp, it's already a transport URL
                replicas = src_file
            else:
                replicas = ctx.getxattr(str(src_file), 'user.replicas')

            io.summary = 'protocol OK-[%s]' % protocol
            io.status = nap.OK

        except gfal2.GError as e:
            io.status = nap.CRITICAL
            er = e.message
            if er:
                io.summary = 'protocol FAILED-[%s]' % protocol + ' [Err:%s]' % str(er)
            else:
                io.summary = 'protocol FAILED-[%s]' % protocol
        except Exception as e:
            io.set_status(
                nap.CRITICAL, 'problem invoking gfal2 getxattr(): %s:%s' %
                (str(e), sys.exc_info()[0]))
     

@app.metric(seq=6, metric_name="VOGet", passive=True)
def metricVOGet(args, io):
    """Copy given remote file(s) from SRM to a local file."""

    # verify previous test succeeded
    results = app.metric_results()
    if ( results[4][1] != nap.OK ):
        io.set_status(nap.WARNING, "VOGet skipped")
        return

    if len(_voInfoDictionary.keys()) == 0:
        io.set_status(nap.WARNING, 'No SRM endpoints found to test')
        return

    for srmendpt in _voInfoDictionary.keys():

        src_filename = (_voInfoDictionary[srmendpt])['fn']
        src_file = srmendpt + '/' + src_filename

        dest_file = 'file://' + _fileTestIn

        # Set transfer parameters
        params = ctx.transfer_parameters()
        params.timeout = args.se_timeout

        params.overwrite = True

        stMsg = 'File was%s copied from SRM.'
        start_transfer = datetime.datetime.now()
        try:
            ctx.filecopy(params, str(src_file), str(dest_file))
            if filecmp.cmp(_fileTest, _fileTestIn):
                # Files match
                io.status = nap.OK
                total_transfer = datetime.datetime.now() - start_transfer
                io.summary = stMsg % (
                    '') + ' Diff successful.' + " Transfer time: " + str(total_transfer)
            else:
                # Files do not match
                io.status = nap.CRITICAL
                io.summary = stMsg % ('') + ' Files differ!'

        except gfal2.GError as e:
            io.status = nap.CRITICAL
            er = e.message
            if er:
                io.summary = stMsg % (' NOT') + ' [Err:%s]' % str(er)
            else:
                io.summary = stMsg % ' NOT'
        except Exception as e:
            io.set_status(
                nap.CRITICAL, 'problem invoking gfal2 filecopy(): %s:%s' %
                (str(e), sys.exc_info()[0]))


@app.metric(seq=7, metric_name="VODel", passive=True)
def metricVODel(args, io):
    """Delete given file(s) from SRM."""

    # skip only if the put failed
    results = app.metric_results()
    if ( results[2][1] != nap.OK ):
        io.set_status(nap.WARNING, "VODel skipped")
        return

    if len(_voInfoDictionary.keys()) == 0:
        io.set_status(nap.CRITICAL, 'No SRM endpoints found to test')

    for srmendpt in _voInfoDictionary.keys():

        src_filename = (_voInfoDictionary[srmendpt])['fn']
        src_file = srmendpt + '/' + src_filename
        stMsg = 'File was%s deleted from SRM.'
        try:
            ctx.unlink(str(src_file))
            io.status = nap.OK
            io.summary = stMsg % ''
        except gfal2.GError as e:
            er = e.message
            if er:
                io.summary = stMsg % ' NOT' + ' [Err:%s]' % str(er)
            else:
                io.summary = stMsg % ' NOT'
            io.status = nap.CRITICAL
        except Exception as e:
            io.set_status(
                nap.CRITICAL, 'problem invoking gfal2 unlink(): %s:%s' %
                (str(e), sys.exc_info()[0]))
 

@app.metric(seq=8, metric_name="VOAll", passive=False)
def metricVOAlll(args, io):
    """Active metric to combine the result from the previous passive ones"""

    results = app.metric_results()

    statuses = [e[1] for e in results]
    
    if all(st == 0 for st in statuses):
        io.set_status(nap.OK, "All fine")
    elif nap.CRITICAL in statuses:
        io.set_status(nap.CRITICAL, "Critical error executing tests")
    else:
        io.set_status(nap.WARNING, "Some of the tests returned a warning")

    try:
        shutil.rmtree(workdir_metric)
    except OSError as e:
        pass


if __name__ == '__main__':
    app.run()