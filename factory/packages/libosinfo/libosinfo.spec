# -*- rpm-spec -*-

%define with_mingw 0
%if 0%{?fedora}
    %define with_mingw 0%{!?_without_mingw:1}
%endif

Summary: A library for managing OS information for virtualization
Name: libosinfo
Version: 1.12.0
Release: 1%{?dist}
License: LGPL-2.1-or-later
Source: https://releases.pagure.org/libosinfo/libosinfo-1.12.0.tar.xz
URL: https://libosinfo.org/

BuildRequires: meson
BuildRequires: gcc
BuildRequires: gtk-doc
BuildRequires: gettext-devel
BuildRequires: glib2-devel
BuildRequires: libxml2-devel >= 2.6.0
BuildRequires: libxslt-devel >= 1.0.0
%if 0%{?fedora} >= 37 || 0%{?rhel} >= 10
BuildRequires: libsoup3-devel
%else
BuildRequires: libsoup-devel
%endif
BuildRequires: vala
BuildRequires: perl-podlators
BuildRequires: hwdata
BuildRequires: gobject-introspection-devel
BuildRequires: osinfo-db
BuildRequires: git
Requires: gobject-introspection
Requires: hwdata
Requires: osinfo-db
Requires: osinfo-db-tools

%if %{with_mingw}
BuildRequires: mingw32-filesystem
BuildRequires: mingw32-gcc
BuildRequires: mingw32-binutils
BuildRequires: mingw32-glib2
BuildRequires: mingw32-libxml2
BuildRequires: mingw32-libxslt
BuildRequires: mingw32-libsoup3

BuildRequires: mingw64-filesystem
BuildRequires: mingw64-gcc
BuildRequires: mingw64-binutils
BuildRequires: mingw64-glib2
BuildRequires: mingw64-libxml2
BuildRequires: mingw64-libxslt
BuildRequires: mingw64-libsoup3
%endif

%description
libosinfo is a library that allows virtualization provisioning tools to
determine the optimal device settings for a hypervisor/operating system
combination.

%package devel
Provides: pkgconfig(libosinfo-1.0) = %{version}
Summary: Libraries, includes, etc. to compile with the libosinfo library
Requires: %{name} = %{version}-%{release}
Requires: pkgconfig
Requires: glib2-devel
# -vala subpackage removed in F30
Obsoletes: libosinfo-vala < 1.3.0-3
Provides: libosinfo-vala = %{version}-%{release}

%description devel
libosinfo is a library that allows virtualization provisioning tools to
determine the optimal device settings for a hypervisor/operating system
combination.

Libraries, includes, etc. to compile with the libosinfo library

%if %{with_mingw}
%package -n mingw32-libosinfo
Summary: %{summary}
BuildArch: noarch

Requires: pkgconfig
Requires: mingw32-osinfo-db
Requires: mingw32-osinfo-db-tools

%description -n mingw32-libosinfo
libosinfo is a library that allows virtualization provisioning tools to
determine the optimal device settings for a hypervisor/operating system
combination.

%package -n mingw64-libosinfo
Summary: %{summary}
BuildArch: noarch

Requires: pkgconfig
Requires: mingw64-osinfo-db
Requires: mingw64-osinfo-db-tools

%description -n mingw64-libosinfo
libosinfo is a library that allows virtualization provisioning tools to
determine the optimal device settings for a hypervisor/operating system
combination.

%{?mingw_debug_package}
%endif

%prep
%autosetup -S git

%build
export CFLAGS="$CFLAGS -Wno-error=deprecated-declarations -DATTRIBUTE_UNUSED='__attribute__((unused))'"
export MINGW32_CFLAGS="%mingw32_cflags -Wno-error=deprecated-declarations -DATTRIBUTE_UNUSED='__attribute__((unused))'"
export MINGW64_CFLAGS="%mingw64_cflags -Wno-error=deprecated-declarations -DATTRIBUTE_UNUSED='__attribute__((unused))'"

%meson \
    -Denable-gtk-doc=true \
    -Denable-tests=true \
    -Denable-introspection=enabled \
    -Denable-vala=enabled
%meson_build

%if %{with_mingw}
%mingw_meson \
    -Denable-gtk-doc=false \
    -Denable-tests=false \
    -Denable-introspection=disabled \
    -Denable-vala=disabled
%mingw_ninja
%endif

%install
%meson_install

%find_lang %{name}

%if %{with_mingw}
%mingw_ninja_install

# Remove static libraries but DON'T remove *.dll.a files.
rm -f $RPM_BUILD_ROOT%{mingw32_libdir}/libosinfo-1.0.a
rm -f $RPM_BUILD_ROOT%{mingw64_libdir}/libosinfo-1.0.a

# Libtool files don't need to be bundled
find $RPM_BUILD_ROOT -name "*.la" -delete

# Manpages don't need to be bundled
rm -rf $RPM_BUILD_ROOT%{mingw32_datadir}/man
rm -rf $RPM_BUILD_ROOT%{mingw64_datadir}/man

rm -rf $RPM_BUILD_ROOT%{mingw32_datadir}/gtk-doc
rm -rf $RPM_BUILD_ROOT%{mingw64_datadir}/gtk-doc

%mingw_debug_install_post

%mingw_find_lang libosinfo
%endif

%check
%meson_test

%ldconfig_scriptlets

%files -f %{name}.lang
%doc AUTHORS ChangeLog COPYING.LIB NEWS README
%{_bindir}/osinfo-detect
%{_bindir}/osinfo-query
%{_bindir}/osinfo-install-script
%{_mandir}/man1/osinfo-detect.1*
%{_mandir}/man1/osinfo-query.1*
%{_mandir}/man1/osinfo-install-script.1*
%{_libdir}/%{name}-1.0.so.*
%{_libdir}/girepository-1.0/Libosinfo-1.0.typelib

%files devel
%{_libdir}/%{name}-1.0.so
%dir %{_includedir}/%{name}-1.0/
%dir %{_includedir}/%{name}-1.0/osinfo/
%{_includedir}/%{name}-1.0/osinfo/*.h
%{_libdir}/pkgconfig/%{name}-1.0.pc
%{_datadir}/gir-1.0/Libosinfo-1.0.gir
%{_datadir}/gtk-doc/html/Libosinfo

%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/libosinfo-1.0.deps
%{_datadir}/vala/vapi/libosinfo-1.0.vapi

%if %{with_mingw}
%files -n mingw32-libosinfo -f mingw32-libosinfo.lang
%doc AUTHORS ChangeLog COPYING.LIB NEWS README
%{mingw32_bindir}/osinfo-detect.exe
%{mingw32_bindir}/osinfo-install-script.exe
%{mingw32_bindir}/osinfo-query.exe
%{mingw32_bindir}/libosinfo-1.0-0.dll
%{mingw32_libdir}/libosinfo-1.0.dll.a
%{mingw32_libdir}/pkgconfig/libosinfo-1.0.pc
%dir %{mingw32_includedir}/libosinfo-1.0/
%dir %{mingw32_includedir}/libosinfo-1.0/osinfo
%{mingw32_includedir}/libosinfo-1.0/osinfo/*.h
%dir %{mingw32_datadir}/libosinfo
%{mingw32_datadir}/libosinfo/usb.ids
%{mingw32_datadir}/libosinfo/pci.ids

%files -n mingw64-libosinfo -f mingw64-libosinfo.lang
%doc AUTHORS ChangeLog COPYING.LIB NEWS README
%{mingw64_bindir}/osinfo-detect.exe
%{mingw64_bindir}/osinfo-install-script.exe
%{mingw64_bindir}/osinfo-query.exe
%{mingw64_bindir}/libosinfo-1.0-0.dll
%{mingw64_libdir}/libosinfo-1.0.dll.a
%{mingw64_libdir}/pkgconfig/libosinfo-1.0.pc
%dir %{mingw64_includedir}/libosinfo-1.0/
%dir %{mingw64_includedir}/libosinfo-1.0/osinfo
%{mingw64_includedir}/libosinfo-1.0/osinfo/*.h
%dir %{mingw64_datadir}/libosinfo
%{mingw64_datadir}/libosinfo/usb.ids
%{mingw64_datadir}/libosinfo/pci.ids
%endif

%changelog
%autochangelog
