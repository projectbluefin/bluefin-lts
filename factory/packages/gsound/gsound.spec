Name:           gsound
Version:        1.0.3
Release:        101%{?dist}
Summary:        Small gobject library for playing system sounds

License:        LGPL-2.1-or-later
URL:            https://wiki.gnome.org/Projects/GSound
Source0:        https://download.gnome.org/sources/gsound/1.0/gsound-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(libcanberra)
BuildRequires:  vala
BuildRequires:  meson

%description
GSound is a small library for playing system sounds. 
It's designed to be used via GObject Introspection, 
and is a thin wrapper around the libcanberra C library

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%setup -q

%build
%meson -Dgtk_doc=false
%meson_build

%install
%meson_install

%ldconfig_scriptlets

%files
%license COPYING
%doc README README.md
%{_bindir}/gsound-play
%{_libdir}/*.so.*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/GSound-1.0.typelib

%files devel
%{_includedir}/*
%{_libdir}/*.so
%{_libdir}/pkgconfig/gsound.pc
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/GSound-1.0.gir
%dir %{_datadir}/vala
%dir %{_datadir}/vala/vapi
%{_datadir}/vala/vapi/gsound.*

%changelog
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 1.0.3-101
- Remove missing man page from files section
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 1.0.3-100
- Initial build for GNOME 50 bootstrap on EL10
