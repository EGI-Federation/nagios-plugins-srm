# Package needs to stay arch specific (due to nagios plugins location), but
# there's nothing to extract debuginfo from
%global debug_package %{nil}

%define nagios_plugins_dir %{_libdir}/nagios/plugins

Name:       nagios-plugins-srm
Version:    0.0.6
Release:    1%{?dist}
Summary:    Nagios probes to be run remotely against SRM mendpoints
License:    ASL 2.0
Group:      Applications/Internet
URL:        https://github.com/EGI-Foundation/nagios-plugins-srm
# The source of this package was pulled from upstream's vcs. Use the
# following commands to generate the tarball:
Source0:   %{name}-%{version}.tar.gz
Buildroot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch: noarch

BuildRequires:  cmake
Requires:   nagios
Requires:   python3.6
Requires:   openldap-clients
Requires:   gfal2-python3
Requires:   python3-nap
Requires:   gfal2-plugin-file
Requires:   gfal2-plugin-srm
Requires:   gfal2-plugin-gridftp
Requires:   gfal2-plugin-xrootd
Requires:   gfal2-plugin-http

%description
This package provides the nagios probes for SRM. 

%prep
%setup -q -n %{name}-%{version}

%build
%cmake . -DCMAKE_INSTALL_PREFIX=/

make %{?_smp_mflags}

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}

make install DESTDIR=%{buildroot}

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{nagios_plugins_dir}/srm
%doc LICENSE README.md

%changelog
* Mom Mar 13 2023 Andrea Manzi <andrea.manzi@egi.eu> - 0.0.6-0
- py3 only version
- added support for srm+https and srm+root
- use new gfal2 credentials API

* Tue Jul 28 2020 Andrea Manzi <amanzi@cern.ch> - 0.0.5-0
- skip tests if dependant tests are failing
- WARNING if LsDir tests returns SRM_TOO_MANY_RESULTS 

* Tue Jun 30 2020 Andrea Manzi <amanzi@cern.ch> - 0.0.4-0
- set credentials via API

* Tue Jun 09 2020 Andrea Manzi <amanzi@cern.ch> - 0.0.3-0
- add gfal2-plugin-gsiftp dependency
- add option to specify proxy path

* Fri May 22 2020 Andrea Manzi <amanzi@cern.ch> - 0.0.2-0
- update spec
- add shebang

* Thu Apr 23 2020 Andrea Manzi <amanzi@cern.ch> - 0.0.1-0
- first version
