Name:           accountsservice
Version:        26.27.3
Release:        1%{?dist}
Summary:        D-Bus interfaces for querying and manipulating user account information
License:        GPL-3.0-or-later
URL:            https://www.freedesktop.org/wiki/Software/AccountsService/
Source0:        https://gitlab.freedesktop.org/accountsservice/accountsservice/-/archive/%{version}/accountsservice-%{version}.tar.bz2

BuildRequires:  gcc
BuildRequires:  gettext-devel
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(json-c) >= 0.15
BuildRequires:  pkgconfig(glib-2.0) >= 2.70
BuildRequires:  polkit-devel
BuildRequires:  systemd
BuildRequires:  systemd-devel
BuildRequires:  gobject-introspection-devel
BuildRequires:  gtk-doc
BuildRequires:  git-core
BuildRequires:  meson
BuildRequires:  vala
BuildRequires:  python3-dbusmock
BuildRequires:  pkgconfig(libxcrypt) >= 4

Requires:       polkit
Requires:       shadow-utils
%{?systemd_requires}

%description
The accountsservice project provides a set of D-Bus interfaces for
querying and manipulating user account information and an implementation
of these interfaces, based on the useradd, usermod and userdel commands.

%package libs
Summary: Client-side library to talk to accountsservice
Requires: %{name}%{?_isa} = %{version}-%{release}

%description libs
The accountsservice-libs package contains a library that can
be used by applications that want to interact with the accountsservice
daemon.

%package devel
Provides: pkgconfig(accountsservice) = %{version}
Summary: Development files for accountsservice-libs
Requires: %{name}-libs%{?_isa} = %{version}-%{release}

%description devel
The accountsservice-devel package contains headers and other
files needed to build applications that use accountsservice-libs.


%prep
%autosetup -S git
# generate-version.sh reads Git tags; preserve the locked release version.
git tag %{version}

%build
%meson \
 -Dgtk_doc=true \
 -Dadmin_group=wheel
%meson_build

%install
%meson_install

mkdir -p $RPM_BUILD_ROOT%{_datadir}/accountsservice/interfaces/

%find_lang accounts-service

%ldconfig_scriptlets libs

%post
%systemd_post accounts-daemon.service

%preun
%systemd_preun accounts-daemon.service

%postun
%systemd_postun accounts-daemon.service

%files -f accounts-service.lang
%license COPYING
%doc README.md AUTHORS
%{_libexecdir}/accounts-daemon
%dir %{_datadir}/accountsservice/
%dir %{_datadir}/accountsservice/interfaces/
%{_datadir}/accountsservice/user-templates/
%{_datadir}/dbus-1/interfaces/org.freedesktop.Accounts.xml
%{_datadir}/dbus-1/interfaces/org.freedesktop.Accounts.User.xml
%{_datadir}/dbus-1/system.d/org.freedesktop.Accounts.conf
%{_datadir}/dbus-1/system-services/org.freedesktop.Accounts.service
%{_datadir}/polkit-1/actions/org.freedesktop.accounts.policy
%dir %{_localstatedir}/lib/AccountsService/
%dir %{_localstatedir}/lib/AccountsService/users/
%dir %{_localstatedir}/lib/AccountsService/icons/
%{_unitdir}/accounts-daemon.service

%files libs
%{_libdir}/libaccountsservice.so.1{,.*}
%dir %{_libdir}/girepository-1.0/
%{_libdir}/girepository-1.0/AccountsService-1.0.typelib

%files devel
%{_includedir}/accountsservice-1.0
%{_libdir}/libaccountsservice.so
%{_libdir}/pkgconfig/accountsservice.pc
%dir %{_datadir}/gir-1.0/
%{_datadir}/gir-1.0/AccountsService-1.0.gir
%dir %{_datadir}/gtk-doc/html/libaccountsservice
%{_datadir}/gtk-doc/html/libaccountsservice/*
%dir %{_datadir}/vala/
%dir %{_datadir}/vala/vapi/
%{_datadir}/vala/vapi/accountsservice.*

%changelog
