Name:           gnome-autoar
Version:        0.4.5
Release:        4%{?dist}
Summary:        Archive library

License:        LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/GNOME/gnome-autoar
Source0:        https://download.gnome.org/sources/%{name}/0.4/%{name}-%{version}.tar.xz


BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gobject-2.0)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(libarchive)

%description
gnome-autoar is a GObject based library for handling archives.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%autosetup -p1


%build
%meson -Dgtk=false \
       -Dvapi=false \
       -Dgtk_doc=false \
       -Dtests=false \
        %{nil}
%meson_build


%install
%meson_install


%check
%meson_test


%files
%license COPYING
%doc NEWS
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/GnomeAutoar-0.1.typelib
%{_libdir}/libgnome-autoar-0.so.0*

%files devel
%{_includedir}/gnome-autoar-0/
%{_libdir}/pkgconfig/gnome-autoar-0.pc
%{_libdir}/*.so
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/GnomeAutoar-0.1.gir


%changelog
* Sat Mar 14 2026 COPR Build <copr@tunaos.org> - 0.4.5-3
- Disable gtk3 widget subpackage (not available on EL10)

* Tue Oct 29 2024 Troy Dawson <tdawson@redhat.com> - 0.4.5-2
- Bump release for October 2024 mass rebuild:
  Resolves: RHEL-64018

* Fri Aug 30 2024 David King <amigadave@amigadave.com> - 0.4.5-1
- Update to 0.4.5

* Mon Jun 24 2024 Troy Dawson <tdawson@redhat.com> - 0.4.4-6
- Bump release for June 2024 mass rebuild

* Fri Feb 09 2024 Ondrej Holy <oholy@redhat.com> - 0.4.4-5
- Migrate to SPDX license

* Wed Jan 24 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.4.4-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Fri Jan 19 2024 Fedora Release Engineering <releng@fedoraproject.org> - 0.4.4-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Wed Jul 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.4.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Sat Mar 18 2023 David King <amigadave@amigadave.com> - 0.4.4-1
- Update to 0.4.4

* Thu Jan 19 2023 Fedora Release Engineering <releng@fedoraproject.org> - 0.4.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Thu Jul 21 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.4.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Sun Feb 13 2022 David King <amigadave@amigadave.com> - 0.4.3-1
- Update to 0.4.3

* Thu Jan 20 2022 Fedora Release Engineering <releng@fedoraproject.org> - 0.4.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Fri Jan 07 2022 David King <amigadave@amigadave.com> - 0.4.2-1
- Update to 0.4.2

* Tue Dec 07 2021 Ondrej Holy <oholy@redhat.com> - 0.4.1-2
- Fix extraction of raw format archives
- Run embedded test suite as a part of the build

* Mon Nov 01 2021 Kalev Lember <klember@redhat.com> - 0.4.1-1
- Update to 0.4.1

* Tue Aug 10 2021 Ondrej Holy <oholy@redhat.com> - 0.4.0-1
- Update to 0.4.0

* Thu Jul 22 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.3.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Mon Jun 21 2021 Kalev Lember <klember@redhat.com> - 0.3.3-1
- Update to 0.3.3

* Wed May 05 2021 Kalev Lember <klember@redhat.com> - 0.3.2-1
- Update to 0.3.2

* Mon Mar 15 2021 Kalev Lember <klember@redhat.com> - 0.3.1-1
- Update to 0.3.1

* Wed Feb 17 2021 Kalev Lember <klember@redhat.com> - 0.3.0-1
- Update to 0.3.0

* Tue Jan 26 2021 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.4-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Sat Aug 01 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.4-4
- Second attempt - Rebuilt for
  https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Mon Jul 27 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.4-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Tue Jan 28 2020 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Tue Jan 07 2020 Kalev Lember <klember@redhat.com> - 0.2.4-1
- Update to 0.2.4

* Thu Jul 25 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.3-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Thu Jan 31 2019 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.3-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Fri Jul 13 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Sat Mar 03 2018 Kalev Lember <klember@redhat.com> - 0.2.3-1
- Update to 0.2.3
- Drop ldconfig scriptlets

* Wed Feb 07 2018 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.2-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Sat Feb 03 2018 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 0.2.2-4
- Switch to %%ldconfig_scriptlets

* Wed Aug 02 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Binutils_Mass_Rebuild

* Wed Jul 26 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.2.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Tue Mar 21 2017 Kalev Lember <klember@redhat.com> - 0.2.2-1
- Update to 0.2.2

* Fri Mar 03 2017 Kalev Lember <klember@redhat.com> - 0.2.1-1
- Update to 0.2.1

* Fri Feb 24 2017 Kalev Lember <klember@redhat.com> - 0.2.0-1
- Update to 0.2.0
- Build with vala support

* Fri Feb 10 2017 Fedora Release Engineering <releng@fedoraproject.org> - 0.1.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Sat Sep 03 2016 Kalev Lember <klember@redhat.com> - 0.1.1-1
- Update to 0.1.1

* Fri Sep 02 2016 Kalev Lember <klember@redhat.com> - 0.1.0-1
- Initial Fedora build
