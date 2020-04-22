#!/bin/sh

# Builder of rpm
# Run it as
# docker run -it -v $PWD:/nagios-plugins-srm centos:7 /nagios-plugins-srm/build.sh

yum install -y epel-release
yum install -y rpm-build epel-rpm-macros  python-pbr git

cd nagios-plugins-srm/

VERSION=$(python setup.py --version)

python setup.py sdist
mkdir -p /root/rpmbuild/SOURCES \
         /root/rpmbuild/SPECS

sed "s/^Version:.*/Version: $VERSION/" nagios-plugins-srm.spec > /root/rpmbuild/SPECS/nagios-plugins-srm.spec

mv dist/nagios_plugins_srm-$VERSION.tar.gz /root/rpmbuild/SOURCES/

rpmbuild -ba  /root/rpmbuild/SPECS/nagios-plugins-srm.spec
mv /root/rpmbuild/RPMS/noarch/* .
