# Nagios-plugins-SRM
![CI](https://github.com/EGI-Foundation/nagios-plugins-srm/workflows/CI/badge.svg)


This is Nagios probe to monitor SRM endpoints executing simple file operations.

It's based on the gfal2 library for the stoerage operations and the python-nap library for execution and reporting.

The probe can query the BDII service in order to build the Storage URL to test given the hostname and the VO name.

A X509 vaild proxy certificate is needed to execute the probe.

## Usage

```
usage: srm_probe.py [-h] [--version] [-H HOSTNAME] [-w WARNING] [-c CRITICAL]
                    [-d] [-p PREFIX] [-s SUFFIX] [-t TIMEOUT] [-C COMMAND]
                    [--dry-run] [-o OUTPUT] [-E ENDPOINT] [-VO VONAME]
                    [--srmv SRMV] [--ldap-url LDAP_URL]
                    [--se-timeout SE_TIMEOUT]

NAGIOS SRM probe

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -H HOSTNAME, --hostname HOSTNAME
                        Host name, IP Address, or unix socket (must be an
                        absolute path)
  -w WARNING, --warning WARNING
                        Offset to result in warning status
  -c CRITICAL, --critical CRITICAL
                        Offset to result in critical status
  -d, --debug           Specify debugging mode
  -p PREFIX, --prefix PREFIX
                        Text to prepend to ever metric name
  -s SUFFIX, --suffix SUFFIX
                        Text to append to every metric name
  -t TIMEOUT, --timeout TIMEOUT
                        Global timeout for plugin execution
  -C COMMAND, --command COMMAND
                        Nagios command pipe for submitting passive results
  --dry-run             Dry run, will not execute commands and submit passive
                        results
  -o OUTPUT, --output OUTPUT
                        Plugin output format; valid options are nagios,
                        check_mk or passive (via command pipe); defaults to
                        nagios)
  -E ENDPOINT, --endpoint ENDPOINT
                        SRM base SURL to test
  -VO VONAME, --voname VONAME
                        VO name, needed for interaction with BDII
  --srmv SRMV           srm version to use
  --ldap-url LDAP_URL   LDAP URL
  --se-timeout SE_TIMEOUT
                        storage operations timeout

```
## Example

```
python srm_probe.py -H ccsrm.in2p3.fr --voname dteam

OK - SURLs successfully retrieved
OK - Storage Path[srm://ccsrm.in2p3.fr:8443/srm/managerv2?SFN=/pnfs/in2p3.fr/data/dteam/] Directory successfully listed
OK - File was copied to SRM. Transfer time: 0:00:01.132255
OK - File successfully listed
OK - protocol OK-[gsiftp]
OK - File was copied from SRM. Diff successful. Transfer time: 0:00:01.491985
OK - File was deleted from SRM.
```