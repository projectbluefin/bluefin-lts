Name:           colord-gtk
Version:        0.3.1
Release:        100%{?dist}
Summary:        GTK4 support library for colord

License:        LGPL-2.1-or-later
URL:            https://github.com/hughsie/colord-gtk
Source0:        https://github.com/hughsie/colord-gtk/archive/refs/tags/%{version}.tar.gz#/colord-gtk-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  gettext-devel
BuildRequires:  pkgconfig(colord) >= 1.3.3
BuildRequires:  pkgconfig(gtk4)

%description
colord-gtk4 provides GTK4 support library for colord, a system service
for managing color devices and ICC profiles.

This package is built without GTK2/GTK3 modules for EL10 compatibility
(EL10 colord-gtk4-devel incorrectly requires colord-gtk-devel which needs gtk3).

%package -n     colord-gtk4
Summary:        GTK4 support library for colord

%description -n colord-gtk4
GTK4 widgets for color device management via colord.

%package -n     colord-gtk4-devel
Summary:        Development files for colord-gtk4
Requires:       colord-gtk4%{?_isa} = %{version}-%{release}
# Explicitly NOT requiring colord-gtk-devel (gtk3-based package)

%description -n colord-gtk4-devel
Development files for building against colord-gtk4.
This package does not require colord-gtk (GTK3) or gtk3-devel.

%prep
%autosetup -n colord-gtk-%{version} -p1

%build
%meson \
    -Dgtk2=false \
    -Dgtk3=false \
    -Dgtk4=true \
    -Dintrospection=false \
    -Dvapi=false \
    -Ddocs=false \
    -Dtests=false \
    -Dman=false
%meson_build

%install
%meson_install
%find_lang colord-gtk

%ldconfig_scriptlets -n colord-gtk4

%files -n colord-gtk4 -f colord-gtk.lang
%license COPYING
%doc README
%{_libdir}/libcolord-gtk4.so.1{,.*}

%files -n colord-gtk4-devel
%{_includedir}/colord-1/colord-gtk.h
%{_includedir}/colord-1/colord-gtk/
%{_libdir}/libcolord-gtk4.so
%{_libdir}/pkgconfig/colord-gtk4.pc

%changelog
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 0.3.1-1
- Build gtk4-only, without gtk2/gtk3 for EL10 compatibility
