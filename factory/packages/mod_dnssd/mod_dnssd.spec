%{!?_httpd_apxs:       %{expand: %%global _httpd_apxs       %%{_sbindir}/apxs}}
%{!?_httpd_mmn:        %{expand: %%global _httpd_mmn        %%(cat %{_includedir}/httpd/.mmn || echo 0-0)}}
%{!?_httpd_confdir:    %{expand: %%global _httpd_confdir    %%{_sysconfdir}/httpd/conf.d}}
# /etc/httpd/conf.d with httpd < 2.4 and defined as /etc/httpd/conf.modules.d with httpd >= 2.4
%{!?_httpd_modconfdir: %{expand: %%global _httpd_modconfdir %%{_sysconfdir}/httpd/conf.d}}

Name:           mod_dnssd
Version:        0.6
Release:        36%{?dist}
Summary:        An Apache HTTPD module which adds Zeroconf support

# Automatically converted from old format: ASL 2.0 - review is highly recommended.
License:        Apache-2.0
URL:            http://0pointer.de/lennart/projects/mod_dnssd/
Source0:        http://0pointer.de/lennart/projects/mod_dnssd/%{name}-%{version}.tar.gz
Source1:        mod_dnssd.conf-httpd
Patch0:         mod_dnssd-0.6-httpd24.patch
Requires:       httpd-mmn = %{_httpd_mmn}
BuildRequires: make
BuildRequires:  gcc
BuildRequires:  httpd-devel avahi-devel e2fsprogs-devel

%description
mod_dnssd is an Apache HTTPD module which adds Zeroconf support via DNS-SD
using Avahi.

%prep
%setup -q
%patch -P0 -p1 -b .httpd24

%build
export APXS=%{_httpd_apxs}
%configure --disable-lynx
make %{?_smp_mflags}

%install
rm -rf $RPM_BUILD_ROOT
install -Dp src/.libs/mod_dnssd.so $RPM_BUILD_ROOT%{_libdir}/httpd/modules/mod_dnssd.so
%if "%{_httpd_confdir}" == "%{_httpd_modconfdir}"
install -Dp -m 0644 %{SOURCE1} $RPM_BUILD_ROOT%{_httpd_confdir}/mod_dnssd.conf
%else
sed -n /^LoadModule/p %{SOURCE1} > 10-mod_dnssd.conf
sed /^LoadModule/d %{SOURCE1} > mod_dnssd.conf
touch -r %{SOURCE1} 10-mod_dnssd.conf mod_dnssd.conf
install -Dp -m 0644 mod_dnssd.conf $RPM_BUILD_ROOT%{_httpd_confdir}/mod_dnssd.conf
install -Dp -m 0644 10-mod_dnssd.conf $RPM_BUILD_ROOT%{_httpd_modconfdir}/10-mod_dnssd.conf
%endif

%files
%doc LICENSE doc/README doc/README.html
%config(noreplace) %{_sysconfdir}/httpd/conf.*/*.conf
%{_libdir}/httpd/modules/mod_dnssd.so

%changelog
* Tue Jan 20 2026 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-36
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Thu Jul 24 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-35
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Fri Jan 17 2025 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-34
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Wed Jul 24 2024 Miroslav Suchý <msuchy@redhat.com> - 0.6-33
- convert license to SPDX

* Thu Jul 18 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-32
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Thu Jan 25 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-31
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sun Jan 21 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-30
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Thu Jul 20 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-29
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-28
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-27
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-26
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-25
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-24
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Jul 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-23
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Wed Jan 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-22
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-21
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Fri Feb 01 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-20
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-19
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Thu Feb 08 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-18
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Thu Aug 03 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-17
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-16
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-15
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Thu Feb 04 2016 Fedora Release Engineering <releng@fedoraproject.org> - 0.6-14
- Rebuilt for https://fedoraproject.org/wiki/Fedora_24_Mass_Rebuild

* Wed Jun 17 2015 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-13
- Rebuilt for https://fedoraproject.org/wiki/Fedora_23_Mass_Rebuild

* Sun Aug 17 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_22_Mass_Rebuild

* Sat Jun 07 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-11
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Thu Jan 23 2014 Joe Orton <jorton@redhat.com> - 0.6-10
- fix _httpd_mmn expansion in absence of httpd-devel

* Sat Aug 03 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Thu Feb 14 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Fri Jul 20 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Tue Apr 17 2012 Joe Orton <jorton@redhat.com> - 0.6-6
- update for httpd 2.4, fix deps etc (#803069)

* Fri Jan 13 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Tue Feb 08 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Sat Jul 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Wed Feb 25 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.6-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Wed Jan 28 2009 Lennart Poettering <lpoetter@redhat.com> - 0.6-1
- New upstream

* Mon Aug 11 2008 Tom "spot" Callaway <tcallawa@redhat.com> - 0.5-7
- fix license tag

* Sun Feb 10 2008 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> 0.5-6
- Rebuild for GCC 4.3

* Mon Sep  3 2007 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> 0.5-5
- Rebuild for new 32-bit APR ABI

* Tue Aug 21 2007 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> 0.5-4
- Fix License tag
- Rebuild for F8t2

* Tue Jul 24 2007 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> 0.5-3
- Add upstream patch to fix UID issue

* Mon Jun 25 2007 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> 0.5-2
- Add LoadModule to the config file

* Mon Jun 18 2007 Ignacio Vazquez-Abrams <ivazqueznet+rpm@gmail.com> 0.5-1
- Initial RPM release
