# Package needs to stay arch specific (due to nagios plugins location), but
# there's nothing to extract debuginfo from
%global debug_package %{nil}

%define nagios_plugins_dir %{_libdir}/nagios/plugins

Name:       nagios-plugins-srm
Version:    0.0.1
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
Requires:   nagios%{?_isa}
Requires:   python%{?_isa}
Requires:   openldap-clients
Requires:   python2-gfal2%{?_isa}
Requires:   python-nap
Requires:   gfal2-plugin-file
Requires:   gfal2-plugin-srm

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
* Thu Apr 23 2020 Andrea Manzi <amanzi@cern.ch> - 0.0.1-0
- first version
