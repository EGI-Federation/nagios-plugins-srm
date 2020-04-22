#
# nagios-plugin-srm RPM
#

%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Summary: Nagios plugins for SRM 
Name: nagios-plugins-srm 
Version: 0.0.1
Release: 1%{?dist}
Group: Applications/Internet
License: ASL 2.0
URL: https://github.com/EGI-Foundation/nagios-plugin-srm
Source: nagios_plugins_srm-%{version}.tar.gz

BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildRequires: python-setuptools
BuildRequires: python-pbr
BuildRequires: python-nap
BuildRequires: python-gfal2
Requires: python-pbr
Requires: python
Requires: openldap-clients
Requires: gfal2-python
Requires: gfal2-plugin-srm
Requires: gfal2-plugin-file


BuildArch: noarch

%description
Nagios plugins for monitoring SRM endpoints

%prep
%setup -q -n nagios_plugins_srm-%{version}

%build

%install
rm -rf $RPM_BUILD_ROOT
python setup.py install --root $RPM_BUILD_ROOT

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%{python_sitelib}/nagios_plugins_srm*
/usr/bin/nagios-plugins-srm

%changelog
* Wed Apr 22 2020 Andrea Manzi <andrea.manzi@egi.eu> 0.0.1
- Initial release 
