%global gettext_version 0.22
%global glib2_version 2.78.3
%global gtk4_version 4.15.2
%global libadwaita_version 1.6~beta
%global libsoup_version 3.0

Name:		gnome-online-accounts
Version:	3.56.4
Release:	1%{?dist}
Summary:	Single sign-on framework for GNOME

# Sources are LGPL-2.0-or-later, icons are CC-BY-SA-4.0.
License:	LGPL-2.0-or-later AND CC-BY-SA-4.0
URL:		https://wiki.gnome.org/Projects/GnomeOnlineAccounts
Source0:	https://download.gnome.org/sources/%{name}/3.56/%{name}-%{version}.tar.xz

BuildRequires:	gcc
BuildRequires:	pkgconfig(dbus-1)
BuildRequires:	pkgconfig(gcr-4)
BuildRequires:	pkgconfig(gio-2.0) >= %{glib2_version}
BuildRequires:	pkgconfig(glib-2.0) >= %{glib2_version}
BuildRequires:	pkgconfig(gobject-2.0) >= %{glib2_version}
BuildRequires:	pkgconfig(gobject-introspection-1.0)
BuildRequires:	pkgconfig(krb5)
BuildRequires:	pkgconfig(libadwaita-1) >= %{libadwaita_version}
BuildRequires:	pkgconfig(libkeyutils)
BuildRequires:	docbook-style-xsl
BuildRequires:	gettext >= %{gettext_version}
BuildRequires:	meson
BuildRequires:	vala
BuildRequires:	/usr/bin/desktop-file-validate
%if !0%{?flatpak}
BuildRequires:	/usr/bin/gi-docgen
BuildRequires:	/usr/bin/xsltproc
BuildRequires:	pkgconfig(gtk4) >= %{gtk4_version}
BuildRequires:	pkgconfig(json-glib-1.0)
BuildRequires:	pkgconfig(libsecret-1)
BuildRequires:	pkgconfig(libsoup-3.0) >= %{libsoup_version}
BuildRequires:	pkgconfig(rest-1.0)
BuildRequires:	pkgconfig(libxml-2.0)
%endif

Requires:	%{name}-libs%{?_isa} = %{version}-%{release}
%if !0%{?flatpak}
Requires:	gvfs-goa
Recommends:	evolution-ews-core
%endif

%description
GNOME Online Accounts provides interfaces so that applications and libraries
in GNOME can access the user's online accounts. It has providers for Google,
Nextcloud, Flickr, Foursquare, Microsoft Account, Microsoft Exchange, Fedora,
IMAP/SMTP and Kerberos.

%package libs
Summary:	Libraries for %{name}

Requires:	glib2%{?_isa} >= %{glib2_version}
%if !0%{?flatpak}
Requires:	gtk4%{?_isa} >= %{gtk4_version}
Requires:	libadwaita%{?_isa} >= %{libadwaita_version}
Requires:	libsoup3%{?_isa} >= %{libsoup_version}
%endif

%description libs
This package contains the libraries for GNOME Online Accounts. It is separated
from the main package to avoid build-time dependency loops.

%package devel
Summary:	Development files for %{name}
Requires:	%{name}-libs%{?_isa} = %{version}-%{release}

%description devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%setup -q

%build
%meson \
%if 0%{?flatpak}
  -Dgoabackend=false \
%else
  -Dfedora=true \
%endif
  %{nil}

%meson_build

%install
%meson_install

%find_lang %{name}

%check
%if !0%{?flatpak}
desktop-file-validate %{buildroot}/%{_datadir}/applications/org.gnome.OnlineAccounts.OAuth2.desktop
%endif

%files -f %{name}.lang
%license COPYING
%doc NEWS README.md
%if !0%{?flatpak}
%{_mandir}/man8/goa-daemon.8*
%{_prefix}/libexec/goa-daemon
%{_prefix}/libexec/goa-identity-service
%{_prefix}/libexec/goa-oauth2-handler
%{_datadir}/applications/org.gnome.OnlineAccounts.OAuth2.desktop
%{_datadir}/dbus-1/services/org.gnome.OnlineAccounts.service
%{_datadir}/dbus-1/services/org.gnome.Identity.service
#%%{_datadir}/glib-2.0/schemas/org.gnome.online-accounts.gschema.xml
%endif
%{_datadir}/icons/hicolor/*/apps/goa-*.svg

%files libs
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/Goa-1.0.typelib
%{_libdir}/libgoa-1.0.so.0
%{_libdir}/libgoa-1.0.so.0.0.0
%if !0%{?flatpak}
%{_libdir}/libgoa-backend-1.0.so.2
%{_libdir}/libgoa-backend-1.0.so.2.0.0
%dir %{_libdir}/goa-1.0
%endif

%files devel
%{_includedir}/goa-1.0/
%{_libdir}/libgoa-1.0.so
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Goa-1.0.gir
%{_libdir}/pkgconfig/goa-1.0.pc
%if !0%{?flatpak}
%{_libdir}/libgoa-backend-1.0.so
%{_libdir}/pkgconfig/goa-backend-1.0.pc
%{_pkgdocdir}/Goa-1.0/
%endif
%{_libdir}/goa-1.0/include
%{_datadir}/vala/

%changelog
* Sun Mar 15 2026 Conductor <james@conductor.local> - 3.56.4-1
- Add gcc BuildRequires for EL10 buildroot compatibility
