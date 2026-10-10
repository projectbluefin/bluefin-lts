Name:           at-spi2-core
Version:        2.60.1
Release:        1%{?dist}
Summary:        Protocol definitions and daemon for D-Bus at-spi

License:        LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/GNOME/%{name}/
Source0:        https://download.gnome.org/sources/at-spi2-core/2.60/at-spi2-core-2.60.1.tar.xz
# scriptlet to set AT_SPI_BUS for XWayland apps that run as root (i.e. anaconda)
# https://bugzilla.redhat.com/show_bug.cgi?id=1821345
Source1:        xwayland-session-scriptlet

BuildRequires:  /usr/bin/sphinx-build
BuildRequires:  gettext
BuildRequires:  gi-docgen
BuildRequires:  gobject-introspection-devel
BuildRequires:  meson
BuildRequires:  python3-devel
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(libei-1.0)
BuildRequires:  pkgconfig(libsystemd)
BuildRequires:  pkgconfig(libxml-2.0)
BuildRequires:  pkgconfig(xi)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  pkgconfig(xtst)

Requires:       dbus
# For xwayland-session-scriptlet
# https://bugzilla.redhat.com/show_bug.cgi?id=2137281
Requires:       /usr/bin/xprop

%description
at-spi allows assistive technologies to access GTK-based
applications. Essentially it exposes the internals of applications for
automation, so tools such as screen readers, magnifiers, or even
scripting interfaces can query and interact with GUI controls.

This version of at-spi is a major break from previous versions.
It has been completely rewritten to use D-Bus rather than
ORBIT / CORBA for its transport protocol.

%package devel
# Expose versions to the dependency preflight before payload Provides exist.
Provides:       pkgconfig(atspi-2) = %{version}

Summary: Development files and headers for at-spi2-core
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
The at-spi2-core-devel package includes the header files and
API documentation for libatspi.

%package -n atk
Summary: Interfaces for accessibility support
# Dependency required for translations.
Requires: at-spi2-core%{?_isa} = %{version}-%{release}

%description -n atk
The ATK library provides a set of interfaces for adding accessibility
support to applications and graphical user interface toolkits. By
supporting the ATK interfaces, an application or toolkit can be used
with tools such as screen readers, magnifiers, and alternative input
devices.

%package -n atk-devel
Summary: Development files for the ATK accessibility toolkit
Requires: atk%{?_isa} = %{version}-%{release}

%description -n atk-devel
This package includes libraries, header files, and developer documentation
needed for development of applications or toolkits which use ATK.

%package -n at-spi2-atk
Summary: A GTK+ module that bridges ATK to D-Bus at-spi
Requires: atk%{?_isa} = %{version}-%{release}
Requires: at-spi2-core%{?_isa} = %{version}-%{release}

%description -n at-spi2-atk
at-spi allows assistive technologies to access GTK-based
applications. Essentially it exposes the internals of applications for
automation, so tools such as screen readers, magnifiers, or even
scripting interfaces can query and interact with GUI controls.

This version of at-spi is a major break from previous versions.
It has been completely rewritten to use D-Bus rather than
ORBIT / CORBA for its transport protocol.

This package includes a gtk-module that bridges ATK to the new
D-Bus based at-spi.

%package -n at-spi2-atk-devel
Summary: A GTK+ module that bridges ATK to D-Bus at-spi
Requires: at-spi2-atk%{?_isa} = %{version}-%{release}

%description -n at-spi2-atk-devel
The at-spi2-atk-devel package includes the header files for the at-spi2-atk
library.

%prep
%autosetup -p1

%build
%meson -Ddocs=true -Ddefault_bus=dbus-broker -Ddbus_daemon=/usr/bin/dbus-daemon -Ddbus_broker=/usr/bin/dbus-broker-launch
%meson_build

%install
%meson_install
install -Dpm 0755 %{SOURCE1} %{buildroot}%{_sysconfdir}/xdg/Xwayland-session.d/00-at-spi

%{find_lang} %{name}

%files -f %{name}.lang
%license COPYING
%doc NEWS README.md
%{_libexecdir}/at-spi2-registryd
%dir %{_datadir}/defaults
%dir %{_datadir}/defaults/at-spi2
%{_datadir}/defaults/at-spi2/accessibility.conf
%{_sysconfdir}/xdg/autostart/at-spi-dbus-bus.desktop
# the 'logical' owner of this dir is gnome-settings-daemon, but g-s-d
# indirectly depends on this package, so depending on it to provide
# this directory would create a circular dependency. so we just co-own
# it instead
%dir %{_sysconfdir}/xdg/Xwayland-session.d
%{_sysconfdir}/xdg/Xwayland-session.d/00-at-spi
%{_libdir}/libatspi.so.*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/Atspi-2.0.typelib
%{_libexecdir}/at-spi-bus-launcher
%dir %{_datadir}/dbus-1/accessibility-services/
%{_datadir}/dbus-1/accessibility-services/org.a11y.atspi.Registry.service
%{_datadir}/dbus-1/services/org.a11y.Bus.service
%{_userunitdir}/at-spi-dbus-bus.service
%dir %{python3_sitearch}/gi/overrides/
%{python3_sitearch}/gi/overrides/Atspi.py
%{python3_sitearch}/gi/overrides/__pycache__/Atspi.*

%files devel
%{_libdir}/libatspi.so
%{_docdir}/libatspi
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Atspi-2.0.gir
%{_includedir}/at-spi-2.0
%{_libdir}/pkgconfig/atspi-2.pc

%files -n atk
%license COPYING
%{_libdir}/libatk-1.0.so.*
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/Atk-1.0.typelib

%files -n atk-devel
%{_libdir}/libatk-1.0.so
%{_includedir}/atk-1.0
%{_libdir}/pkgconfig/atk.pc
%{_docdir}/atk
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Atk-1.0.gir

%files -n at-spi2-atk
%license COPYING
%dir %{_libdir}/gtk-2.0
%dir %{_libdir}/gtk-2.0/modules
%{_libdir}/gtk-2.0/modules/libatk-bridge.so
%{_libdir}/gnome-settings-daemon-3.0/gtk-modules/at-spi2-atk.desktop
%{_libdir}/libatk-bridge-2.0.so.*

%files -n at-spi2-atk-devel
%{_includedir}/at-spi2-atk/2.0/atk-bridge.h
%{_libdir}/libatk-bridge-2.0.so
%{_libdir}/pkgconfig/atk-bridge-2.0.pc

%changelog
%autochangelog
