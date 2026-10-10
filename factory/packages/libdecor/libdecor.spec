Name:           libdecor
Version:        0.2.2
Release:        100%{?dist}
Summary:        Client-side decorations library for Wayland clients

License:        MIT
URL:            https://gitlab.freedesktop.org/libdecor/libdecor
Source0:        https://gitlab.freedesktop.org/libdecor/libdecor/-/archive/%{version}/libdecor-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(wayland-protocols) >= 1.18
BuildRequires:  pkgconfig(wayland-server)
BuildRequires:  pkgconfig(xkbcommon)

%description
libdecor is a library that can help Wayland clients draw window
decorations. It aims to provide multiple backends to draw decorations.

This package is built without the GTK3 plugin for EL10 compatibility
(EL10 libdecor requires gtk3 which has been removed).

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
Development files for libdecor.

%prep
%autosetup -p1

%build
%meson \
    -Dgtk=disabled \
    -Ddemo=false
%meson_build

%install
%meson_install

%ldconfig_scriptlets

%files
%license LICENSE
%doc README.md
%{_libdir}/libdecor-0.so.0{,.*}
%dir %{_libdir}/libdecor/
%{_libdir}/libdecor/plugins-1/

%files devel
%{_includedir}/libdecor-0/
%{_libdir}/libdecor-0.so
%{_libdir}/pkgconfig/libdecor-0.pc

%changelog
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 0.2.2-1
- Build without GTK3 plugin for EL10 compatibility
  (EL10 libdecor requires gtk3 which has been removed)
