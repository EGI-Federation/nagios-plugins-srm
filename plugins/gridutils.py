##############################################################################
#
# NAME:        gridutils.py
#
# FACILITY:    SAM (Service Availability Monitoring)
#
# COPYRIGHT:
#         Copyright (c) 2009, Members of the EGEE Collaboration.
#         http://www.eu-egee.org/partners/
#         Licensed under the Apache License, Version 2.0.
#         http://www.apache.org/licenses/LICENSE-2.0
#         This software is provided "as is", without warranties
#         or conditions of any kind, either express or implied.
#
# DESCRIPTION:
#
#         Grid utility functions for 'gridmon' package.
#
# AUTHORS:     Konstantin Skaburskas, CERN
#
# CREATED:     28-May-2009
#
##############################################################################

"""
Grid utility functions.
"""

import sys
import re
import subprocess
import socket
from random import choice

LDAP_TIMEOUT_NETWORK = 20
LDAP_TIMELIMIT_SEARCH = 20

class ErrLDAPTimeout(Exception):
    """LDAP timeout exception.
    """


# Return codes in case of LDAP query errors
LDAP_QE_EMPTYSET = 0
LDAP_QE_LDAP = 1
LDAP_QE_TIMEOUT = 2
LDAP_QE_OTHER = 7


def query_bdii(ldap_filter, ldap_attrlist, ldap_url='', ldap_base='o=grid',
               ldap_timelimit=LDAP_TIMELIMIT_SEARCH,
               net_timeout=LDAP_TIMEOUT_NETWORK):
    """Query BDII (LDAP based).

    Depending on availability uses either LDAP API or CLI.

    @param ldap_filter: non-empty filter.
    @type ldap_filter: L{str}
    @param ldap_attrlist: list of attributes to search for.
    @type ldap_attrlist: L{list}
    @param ldap_url: (default: '') if not given, C{LCG_GFAL_INFOSYS} will be used.
      ldap://<hostname|ip>:port. Comma-separated list is possible.
    @type ldap_url: L{str}
    @param ldap_timelimit: LDAP internal search time limit (default: L{LDAP_TIMELIMIT_SEARCH})
    @type ldap_timelimit: L{int}
    @param net_timeout: connection timeout (default: L{LDAP_TIMEOUT_NETWORK}).
    @type net_timeout: L{int}

    @return:
      - on success:
          - (1, [entries]) - entries : list of tuples as query results
            C{('<LDAPnameSpace>', {'<attribute>': ['<value>',..],..})}. Eg.:
              - ('GlueSALocalID=ops,...,Mds-Vo-name=local,o=grid',
                {'GlueSAStateAvailableSpace': ['197000000000']})
      - on failure:
          - (0, (N, summary, detmsg))
              - N - 0 : query returned empty set
              - N - 1 : CLI/API or LDAP problem (eg., CLI: "command not found")
              - N - 2 : timeout
    @rtype: L{tuple}
    """
    if not ldap_filter:
        msg = 'ldap_filer must be specified (%s())' % \
            sys._getframe(1).f_code.co_name
        return 0, (LDAP_QE_OTHER, msg, msg)

    if not isinstance(ldap_attrlist, list):
        msg = 'attributes list should be a list object (%s())' % \
            sys._getframe(1).f_code.co_name
        return (0, (LDAP_QE_OTHER, msg, msg))

    ldaps = ldap_url and ldap_url.split(',') or \
        sys.get_env('LCG_GFAL_INFOSYS').split(',')
    try:
        ldap_url = get_working_ldap(ldaps)  # IP address
    except (TypeError, ValueError, LookupError) as e:
        return 0, (LDAP_QE_OTHER, 'Failed to get working BDII from [%s].' % ','.join(
            ldaps), str(e))
    try:

        return __ldap_CLI(ldap_filter, ldap_attrlist, ldap_url,
                          ldap_base, ldap_timelimit, net_timeout)
    except Exception as e:
        return 0, (LDAP_QE_OTHER,
                   'Exception while querying BDII [%s]' % ldap_url, str(e))


def __ldap_CLI(ldap_filter, ldap_attrlist, ldap_url, ldap_base, ldap_timelimit,
               net_timetout):
    """Query LDAP using CLI.

    For signature see L{query_bdii()}
    """

    if not isinstance(ldap_attrlist, list):
        stsmsg = detmsg = 'Error invoking LDAP search CPI: attributes ' + \
            'list should be a list.'
        return (0, (LDAP_QE_OTHER, stsmsg, detmsg))

    bdii = to_full_bdii_url(ldap_url)

    cmd = "ldapsearch -l %i -x -LLL -h %s -b %s %s %s" % \
        (ldap_timelimit, bdii, ldap_base, ldap_filter,
         ' '.join([x for x in ldap_attrlist]))

    res = ''
    try:

        res = subprocess.check_output(cmd.split(' '))
        res = res.decode(encoding='utf-8', errors='strict')

    except ErrLDAPTimeout:
        stsmsg = detmsg = 'LDAP search timed out after %i sec. %s' % \
            (ldap_timelimit, bdii)
        return (0, (LDAP_QE_TIMEOUT, stsmsg, detmsg))
    except Exception as e:
        stsmsg = '%s %s' % (str(e).strip(), bdii)
        detmsg = '%s\n%s' % (cmd, stsmsg)
        return (0, (LDAP_QE_LDAP, stsmsg, detmsg))

    if res:
        # remove line foldings made by ldapsearch
        res = res.replace('\n ', '').strip()
        entries = []
        res = res.split('dn: ')
        # loop through values in "dn:"
        for dn in res:
            if dn:
                dl = dn.splitlines()
                # remove empty lines
                for i, v in enumerate(dl):
                    if not v:
                        del dl[i]
                # make dict key/value pairs out
                # of Glue "Attribute: Value" pairs
                d = {}
                for x in dl[1:]:
                    t = x.split(':', 1)
                    t[0] = t[0].strip()
                    t[1] = t[1].strip()
                    if t[0] in d:
                        d[t[0]].append(t[1])
                    else:
                        d[t[0]] = [t[1]]
                entries.append((dl[0], d))
        return (1, (entries))
    else:
        return __return_query_failed_emtpy_set(ldap_url, ldap_attrlist,
                                               ldap_filter, ldap_base)


def __return_query_failed_emtpy_set(
        ldap_url,
        ldap_attrlist,
        ldap_filter,
        ldap_base):
    """Formatted output on empty set returned by a query."""
    ldap_url = ldap_url2hostname_ip(ldap_url)
    stsmsg = 'No information for [attribute(s): %s] in %s.' % \
        (ldap_attrlist, ldap_url)
    detmsg = 'No information for [base: %s; filter: %s; attribute(s): %s] in %s.' % (
        ldap_base, ldap_filter, ldap_attrlist, ldap_url)
    return (0, (LDAP_QE_EMPTYSET, stsmsg, detmsg))


def get_working_ldap(ldaps, net_timeout=LDAP_TIMEOUT_NETWORK):
    """Test given list of LDAP servers and return a first working one as IP
    address.

    Depending on availability uses either LDAP API or CLI.

    @param  ldaps: list of LDAP endpoints (ldap://<hostname>:[<port>]).
    @type ldaps: L{list}
    @param net_timeout: connection timeout (default: L{LDAP_TIMEOUT_NETWORK}).
    @type net_timeout: L{int}

    @return:
      - on success:
          - C{endpoint} - first working LDAP endpoint as IP address
    @rtype: L{str}

    @raises LookupError,TypeError,ValueError:
      - LookupError - if no working endpoints found.
      - TypeError - L{ldaps} must be a list object.
      - ValueError - list of empty endpoints or empty list is given.
    """

    if not isinstance(ldaps, list):
        raise TypeError('ldaps should be a list object.')
    len(ldaps)
    if len(ldaps) == 0:
        raise ValueError('Empty LDAP endpoints list given (%s()).' %
                         sys._getframe(0).f_code.co_name)
    else:
        i = 0
        for v in ldaps:
            if not v:
                i += 1
        if i == len(ldaps):
            raise ValueError('List of empty LDAP endpoints given (%s()).' %
                             sys._getframe(0).f_code.co_name)
    failed_ldaps = {}
    for ldap_url in ldaps:
        proto, hostname, port = parse_uri3(ldap_url)
        try:
            ips = dns_lookup_forward(hostname)
        except IOError as e:
            # Forward DNS resolution failed. Continue with the next host.
            failed_ldaps[ldap_url] = str(e)
            continue
        else:
            for ip in ips:
                ldap_url_ip = '%s%s:%s' % (proto or '', ip, port)

                rc, error = __ldap_bind_CLI(ldap_url_ip, net_timeout)
                if rc:
                    return ldap_url_ip
                host_ip = ldap_url2hostname_ip(ldap_url_ip)
                failed_ldaps[host_ip] = error
    msg = ''
    for k, v in failed_ldaps.items():
        msg = '%s* %s: %s' % (msg and msg + '\n' or '', k, v)
    raise LookupError(msg)


def __ldap_bind_CLI(url, net_timeout):
    """Bind to LDAP using CLI.

    @param url: LDAP URI (ldap://<hostname>:[<port>]).
    @type url: L{str}
    @param net_timeout: network timeout
    @type net_timeout: L{int}

    @return:
      - on success: C{(1, '')}
      - on failure: C{(0, 'error message')}
    @rtype: L{tuple}
    """
    cmd = 'ldapsearch -xLLL -h %s' % (to_full_bdii_url(url))

    rc = subprocess.call(cmd.split(" "))

    if rc not in (0, 32):  # No such object (32)
        return 0, '%i' % (rc)
    return 1, ''


def to_full_ldap_url(url, port='2170'):
    """Given LDAP url return full LDAP uri.
    Keyword argument C{port} is used if url:port wasn't found in the given url.

    @return: ldap://<url:hostname>:<url:port>.
    """
    hp = parse_uri3(url)
    if not hp[0]:
        hp[0] = 'ldap://'
    if not hp[2]:
        hp[2] = port
    return '%s%s:%s' % (hp[0], hp[1], hp[2])


def to_full_bdii_url(url, port='2170'):
    """Given url return <url:hostname>:<url:port>.

    @return: <url:hostname>:<url:port>.
    """
    hp = parse_uri(url)
    if not hp[1]:
        hp[1] = port
    return '%s:%s' % (hp[0], hp[1])


def dns_lookup_reverse(ip):
    """Reverse DNS lookup.

    :param ip: valid IP as string
    :type ip: `str`
    :return: hostname
    :rtype: `str`
    :raises ValueError,IOError:
      - ValueError - not valid IP address given
      - IOError - on any hostname resolution errors
    """
    try:
        socket.inet_aton(ip)
    except socket.error:
        raise ValueError('Not valid IP address given: %r' % ip)
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
    except (socket.gaierror, socket.herror) as e:
        raise IOError(str(e))
    return hostname


def ldap_url2hostname_ip(ldap_url):
    """Given LDAP URL, return
      - [ldap://hostname:port [ip]] - if ldap_url based on IP address
      - [ldap://hostname:port] - in other cases

    :rtype: `str`
    """
    host, port = parse_uri2(ldap_url)
    try:
        socket.inet_aton(host)
        hostname = dns_lookup_reverse(host)
    except (socket.error, IOError):
        return '[ldap://%s%s]' % (host, port and ':' + port or '')
    else:
        return '[ldap://%s%s [%s]]' % (hostname, port and ':' + port or '',
                                       host)


def dns_lookup_forward(hostname):
    """Forward DNS lookup.

    :param hostname: hostname
    :type hostname: `str`
    :return: list of IPs as strings
    :rtype: `list`
    :raises ValueError,IOError:
      - ValueError - on empty hostname
      - IOError - on any IP address resolution errors
    """
    if not hostname:
        raise ValueError('Empty hostname provided.')
    try:
        _, _, ips = socket.gethostbyname_ex(hostname)
    except (socket.gaierror, socket.herror) as e:
        raise IOError(str(e))
    return ips


def parse_uri(uri):
    """Return [host, port] from given URI.

    :param uri: one of:
      ``proto://host/``,
      ``proto://host:port/``,
      ``proto://host``,
      ``proto://host:port``,
      ``host``,
      ``host:port``;
      where ``proto`` can be ``[a-zA-Z0-9_]*``. Eg.: ``srm_v1``.
    :type uri: `str`
    :return: [host, port]
    :rtype: `list`
    """
    match = re.match(r'([a-zA-Z0-9_]*://)?([^/:$]*):?(\d+)?/?', uri)
    return [match.group(2), match.group(3)]


parse_uri2 = parse_uri
"alias to `parse_uri()`; two-element list [host, port] is returned."


def uuidstr(len=12, chars='0123456789abcdef'):
    """Pseudo-random string of a given length based on a set of chars.

    :param len: length of string to be generated
    :type len: `int`
    :param chars: alphabet to generate from
    :type chars: `str`
    :return: `str`
    """
    return ''.join([choice(chars) for i in range(len)])


def parse_uri3(uri):
    """Return [proto, host, port] from given URI.

    :param uri: see `parse_uri()`
    :return: [proto, host, port]
    :rtype: `list`
    """
    m = re.match(r'([a-zA-Z0-9_]*://)?([^/:$]*):?(\d+)?/?', uri)
    return [m.group(1), m.group(2), m.group(3)]
