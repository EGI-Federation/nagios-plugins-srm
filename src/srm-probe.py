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
import logging
import filecmp
import gfal2
import nap.core
import shutil

try:
    from urlparse import urlparse
except BaseException:
    from urllib.parse import urlparse


PROBE_VERSION = "v0.0.1"

# logging
log = logging.getLogger("SRM-PROBE")
log.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt='%(message)s')
fh = logging.StreamHandler(stream=sys.stdout)
fh.setFormatter(formatter)
log.addHandler(fh)

# ########################################################################### #
app = nap.core.Plugin(description="ARGO SRM endpoint probe",
                      version=PROBE_VERSION)
app.add_argument("-E", "--endpoint", help="endpoint")
app.add_argument("-VO", "--voname", help="voname")
app.add_argument("-4", "--ipv4", help="use IP v4 protocol for probing",
                 action="store_true")
app.add_argument("-6", "--ipv6", help="use IP v6 protocol for probing",
                 action="store_true")
app.add_argument("-X", "--x509", help="location of x509 certificate file")
app.add_argument("-srm", "--srmv", help="srm version")
app.add_argument("-l", "--ldap-uri", help="ldap-uri")
app.add_argument("-timeout", "--se-timeout", help="se timeout")


# Reasonable defaults for timeouts
LCG_GFAL_BDII_TIMEOUT = 10

gfal2.set_verbose(gfal2.verbose_level.debug)
# Service version(s)
svcVers = ['1', '2']  # NOT USED YET
svcVer = '2'
ldap_url = "ldap://lcg-bdii.cern.ch:2170"

workdir_metric = tempfile.mkdtemp()

# files and patterns
_fileTest = workdir_metric + '/testFile.txt'
_fileTestIn = workdir_metric + '/testFileIn.txt'
_fileSRMPattern = 'testfile-put-%s-%s.txt'  # time, uuid

_voInfoDictionary = {}

voName = "dteam"

# GFAL version
gfal2_ver = "gfal2 " + gfal2.get_version()


def parse_args(args):
    pass
    # for o,v in args:
    #     if o in ('--srmv'):
    #         if v in svcVers:
    #             svcVer = str(v)
    #         else:
    #             errstr = '--srmv must be one of '+\
    #                 ', '.join([x for x in svcVers])+'. '+v+' given.'
    #             raise getopt.GetoptError(errstr)
    #     elif o in ('--ldap-uri'):
    #         [host, port] = gridutils.parse_uri(v)
    #         if port == None or port == '':
    #             port = '2170'
    #         _ldap_url = 'ldap://'+host+':'+port
    #         os.environ['LCG_GFAL_INFOSYS'] = host+':'+port
    #     elif o in ('--ldap-timeout'):
    #         _timeouts['ldap_timelimit'] = int(v)
    #     elif o in ('--se-timeout'):
    #         _timeouts['srm_connect'] = int(v)


def query_bdii(ldap_filter, ldap_attrlist, ldap_url=''):
    'Local wrapper for gridutils.query_bdii()'

    ldap_url = ldap_url

    log.debug('Query BDII.')
    log.debug('''Parameters:
ldap_url: %s
ldap_timelimit: %i
ldap_filter: %s
ldap_attrlist: %s''' % (ldap_url, LCG_GFAL_BDII_TIMEOUT, ldap_filter, ldap_attrlist))

    log.debug('Querying BDII %s' % ldap_url)
    rc, qres = gridutils.query_bdii(ldap_filter, ldap_attrlist,
                                    ldap_url=ldap_url,
                                    ldap_timelimit=LCG_GFAL_BDII_TIMEOUT)
    log.debug(qres)
    return rc, qres


@app.metric(seq=1, metric_name="GetSURLs", passive=False)
def getSURL(args, io):
    # working directory for metrics
    log.debug(workdir_metric)
    parse_args(args)

    ldap_f = "(|(&(GlueChunkKey=GlueSEUniqueID=%s)(|(GlueSAAccessControlBaseRule=%s)(GlueSAAccessControlBaseRule=VO:%s)))" \
        + "(&(GlueChunkKey=GlueSEUniqueID=%s)(|(GlueVOInfoAccessControlBaseRule=%s)(GlueVOInfoAccessControlBaseRule=VO:%s)))" \
        + "(&(GlueServiceUniqueID=*://%s*)(GlueServiceVersion=%s.*)(GlueServiceType=srm*)))"
    ldap_filter = ldap_f % (args.endpoint, voName, voName, args.endpoint, voName, voName, args.endpoint, svcVer)
    ldap_attrlist = ['GlueServiceEndpoint', 'GlueSAPath', 'GlueVOInfoPath']

    rc, qres = query_bdii(ldap_filter, ldap_attrlist, ldap_url)
    if not rc:
        if qres[0] == 0:  # empty set
            io.status = nap.CRITICAL
        else:  # all other problems
            io.status = nap.UNKNOWN
        log.debug(qres[2])
        io.summary = "Error querying the BDII"
        return

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
                      (k, args.endpoint, ldap_url))
        return
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
        return
    else:
        endpoint = res[k][0]

    log.debug('GlueServiceEndpoint: %s' % endpoint)

    if res['GlueVOInfoPath']:
        storpaths = res['GlueVOInfoPath']
        log.debug('GlueVOInfoPath: %s' % ', '.join(storpaths))
    elif res['GlueSAPath']:
        storpaths = res['GlueSAPath']
        log.debug('GlueSAPath: %s' % ', '.join(storpaths))
    else:
        # GlueSAPath or GlueVOInfoPath is not published
        io.set_status(
            nap.CRITICAL, "GlueVOInfoPath or GlueSAPath not published for %s in %s" %
            (res['GlueServiceEndpoint'][0], ldap_url))
        return

    eps = [
        endpoint.replace(
            'httpg',
            'srm',
            1) +
        '?SFN=' +
        sp for sp in storpaths]
    log.debug('SRM endpoint(s) to test:')
    log.debug('\n'.join(eps).strip('\n'))

    log.debug('Saving endpoints to cache')

    for ep in eps:
        _voInfoDictionary[ep] = {}
    io.summary = 'SURL successfully stored'
    io.status = nap.OK


@app.metric(seq=2, metric_name="VOLsDir", passive=False)
def metricVOLsDir(args, io):
    """
    List content of VO's top level space area(s) in SRM using gfal2.listdir().
    """
    srms = []
    try:
        for srm in _voInfoDictionary.keys():
            srms.append(srm)
        if not srms:
            io.set_status(nap.CRITICAL, 'No SRM endpoints found in cache')
            return
    except Exception as e:
        log.debug('ERROR: %s' % str(e))
        io.set_status('UNKNOWN', 'Error reading SRM to test')
        return

    log.debug('Using gfal2 listdir()')

    # Instantiate gfal2
    ctx = gfal2.creat_context()

    log.debug('Listing storage url(s).')

    for surl in srms:
        io.summary = 'Storage Path[%s]' % surl
        log.debug('Storage Path[%s]' % surl)
        try:
            ctx.listdir(surl)
            io.summary = 'Directory successfully listed'
            io.status = nap.OK
        except gfal2.GError as e:
            er = e.message
            io.status = nap.CRITICAL
            if er:
                io.summary = '%d [Err:%s];' % (io.status, str(er))
            else:
                io.summary = '%d' % io.status
            log.debug('ERROR: %s\n' % (e.message))
        except Exception as e:
            io.set_status(
                nap.UNKNOWN, 'problem invoking gfal2 listdir(): %s:%s' %
                (str(e), sys.exc_info()[0]))


@app.metric(seq=3, metric_name="VOPut", passive=False)
def metricVOPut(args, io):
    """Copy a local file to the SRM into space area(s) defined by VO."""

    def event_callback(event):
        log.debug(
            "[%s] %s %s %s" %
            (event.timestamp,
             event.domain,
             event.stage,
             event.description))

    log.debug(gfal2_ver)
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
            io.set_status(nap.CRITICAL, 'No SRM endpoints found in cache')
    except IOError as e:
        log.debug('ERROR: %s' % str(e))
        return ('UNKNOWN', 'Error creating source file')

    # Instantiate gfal2
    ctx = gfal2.creat_context()

    for dest_file in dest_files:
        # Set transfer parameters
        params = ctx.transfer_parameters()
        params.create_parent = True
        params.timeout = 30
        params.event_callback = event_callback

        log.debug('VOPut: Copy file using gfal.filecopy().')

        log.debug('''Parameters:
 source: %s
 dest: %s
 src_spacetoken: %s
 dst_spacetoken: %s
 timeout: %s''' % (src_file, dest_file, params.src_spacetoken,
                   params.dst_spacetoken, params.timeout))

        start_transfer = datetime.datetime.now()
        log.debug('StartTime of the transfer: %s' % str(start_transfer))

        stMsg = 'File was%s copied to SRM.'

        try:
            ctx.filecopy(params, "file://" + src_file, dest_file)
            total_transfer = datetime.datetime.now() - start_transfer
            log.debug('Transfer Duration: %s' % str(total_transfer))
            io.summary = stMsg % '' + " Transfer time: " + str(total_transfer)
            io.status = nap.OK
        except gfal2.GError as e:
            io.status = nap.CRITICAL
            er = e.message
            if er:
                io.summary = stMsg % (' NOT') + ' [Err:%s]' % str(er)
            else:
                io.summary = stMsg % ' NOT'
                log.debug('ERROR: %s' % str(e))
        except Exception as e:
            io.status = nap.UNKNOWN
            io.summary = stMsg % ' NOT'
            log.debug('ERROR: %s:%s' % (str(e), sys.exc_info()[0]))


@app.metric(seq=4, metric_name="VOLs", passive=False)
def metricVOLs(args, io):
    """Stat (previously copied) file(s) on the SRM."""
    log.debug(gfal2_ver)

    srms = []

    for srmendpt in _voInfoDictionary.keys():
        dest_filename = (_voInfoDictionary[srmendpt])['fn']
        dest_file = srmendpt + '/' + dest_filename
        srms.append(dest_file)

    log.debug('Using gfal2.stat().')
    log.debug('Stating file(s).')

    # Instantiate gfal2
    ctx = gfal2.creat_context()

    for surl in srms:
        log.debug('listing [%s]' % surl)
        try:
            statp = ctx.stat(surl)
            log.debug("stat: " + str(statp).replace('\n', ', '))
            io.summary = 'ok;'
            io.status = nap.OK
        except gfal2.GError as e:
            er = e.message
            io.status = nap.CRITICAL
            if er:
                io.summary = '%d [Err:%s];' % (io.status, str(er))
            else:
                io.summary = '%d;' % io.status
            log.debug('ERROR: %s' % e.message)
        except Exception as e:
            io.set_status(
                nap.UNKNOWN, 'problem invoking gfal2 stat(): %s:%s' %
                (str(e), sys.exc_info()[0]))


@app.metric(seq=5, metric_name="VOGetTurl", passive=False)
def metricVOGetTURLs(ags, io):
    """Get Transport URLs for the file copied to storage"""

    log.debug(gfal2_ver)

    # Instantiate gfal2
    ctx = gfal2.creat_context()

    for srmendpt in _voInfoDictionary.keys():

        src_filename = (_voInfoDictionary[srmendpt])['fn']
        src_file = srmendpt + '/' + src_filename
        protocol = 'gsiftp'
        try:
            if urlparse(src_file).scheme == 'gsiftp':
                # If protocol is gsiftp, it's already a transport URL
                replicas = src_file
            else:
                log.debug('Using gfal2.xattr.')
                replicas = ctx.getxattr(src_file, 'user.replicas')

            log.debug('proto: %s OK' % protocol)
            log.debug('replicas: %s' % replicas)
            io.summary = 'protocol OK-[%s]' % protocol
            io.status = nap.OK

        except gfal2.GError as e:
            io.status = nap.CRITICAL
            io.summary = 'protocol FAILED-[%s]' % protocol
            log.debug('error: %s' % e.message)
        except Exception as e:
            io.status = nap.UNKNOWN
            log.debug('ERROR: %s\n%s' % (str(e), sys.exc_info()[0]))


@app.metric(seq=6, metric_name="VOGet", passive=False)
def metricVOGet(args, io):
    """Copy given remote file(s) from SRM to a local file."""

    def event_callback(event):
        log.debug(
            "[%s] %s %s %s" %
            (event.timestamp,
             event.domain,
             event.stage,
             event.description))

    log.debug(gfal2_ver)

    # Instantiate gfal2
    ctx = gfal2.creat_context()

    for srmendpt in _voInfoDictionary.keys():

        src_filename = (_voInfoDictionary[srmendpt])['fn']
        src_file = srmendpt + '/' + src_filename

        dest_file = 'file://' + _fileTestIn

        log.debug('Source: %s' % src_file)
        log.debug('Destination: %s' % dest_file)

        # Set transfer parameters
        params = ctx.transfer_parameters()
        params.timeout = 30
        params.event_callback = event_callback

        params.overwrite = True

        log.debug('Get file using gfal.filecopy().')

        log.debug('''Parameters:
 source: %s
 dest: %s
 src_spacetoken: %s
 dst_spacetoken: %s
 timeout: %s''' % (src_file, dest_file, params.src_spacetoken,
                   params.dst_spacetoken, params.timeout))

        stMsg = 'File was%s copied from SRM.'
        start_transfer = datetime.datetime.now()
        log.debug('StartTime of the transfer: %s' % str(start_transfer))

        try:
            ctx.filecopy(params, src_file, dest_file)
            if filecmp.cmp(_fileTest, _fileTestIn):
                # Files match
                io.status = nap.OK
                total_transfer = datetime.datetime.now() - start_transfer
                log.debug('Transfer Duration: %s' % str(total_transfer))
                io.summary = stMsg % (
                    '') + ' Diff successful.' + " Transfer time: " + str(total_transfer)
            else:
                # Files do not match
                io.status = nap.CRITICAL
                io.summary = stMsg % ('') + ' Files differ!'
                log.debug('Files differ!')
        except gfal2.GError as e:
            io.status = nap.CRITICAL
            er = e.message
            if er:
                io.summary = stMsg % (' NOT') + ' [Err:%s]' % str(er)
            else:
                io.summary = stMsg % ' NOT'
            log.debug('ERROR: %s' % str(e))
        except Exception as e:
            io.status = 'UNKNOWN'
            io.summary = stMsg % ' NOT'
            log.debug('ERROR: %s:%s' % (str(e), sys.exc_info()[0]))


@app.metric(seq=7, metric_name="VODel", passive=False)
def metricVODel(args, io):
    """Delete given file(s) from SRM."""
    log.debug(gfal2_ver)

    # Instantiate gfal2
    ctx = gfal2.creat_context()

    for srmendpt in _voInfoDictionary.keys():

        src_filename = (_voInfoDictionary[srmendpt])['fn']
        src_file = srmendpt + '/' + src_filename

        log.debug('Source: %s' % src_file)
        log.debug('Using gfal2.unlink().')

        stMsg = 'File was%s deleted from SRM.'

        log.debug('Deleting: %s' % src_file)
        try:
            ctx.unlink(src_file)
            io.status = nap.OK
            io.summary = stMsg % ''
        except gfal2.GError as e:
            io.summary = stMsg % ' NOT'
            io.status = nap.CRITICAL
            log.debug('ERROR: %s:%s' % (str(e), sys.exc_info()[0]))
        except Exception as e:
            io.status = nap.UNKNOWN
            io.summary = stMsg % ' NOT'
            log.debug('ERROR: %s:%s' % (str(e), sys.exc_info()[0]))
    try:
        shutil.rmtree(workdir_metric)
    except OSError as e:
        print("Error: %s : %s" % (workdir_metric, e.strerror))


app.run()
