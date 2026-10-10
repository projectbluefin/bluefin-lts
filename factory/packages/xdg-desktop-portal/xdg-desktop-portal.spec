%bcond docs %{undefined rhel}

%global flatpak_version 1.5.0
%global geoclue_version 2.5.2
%global glib_version 2.76
%global low_memory_monitor_version 2.0
%global pipewire_version 0.2.90

Name:    xdg-desktop-portal
Version: 1.21.0
Release: %autorelease
Summary: Portal frontend service to flatpak

# doc/website is CC0-1.0 but it is not included in rpm
License: LGPL-2.1-or-later
URL:     https://github.com/flatpak/xdg-desktop-portal/
Source0: https://github.com/flatpak/xdg-desktop-portal/releases/download/%{version}/%{name}-%{version}.tar.xz

BuildRequires: gcc
BuildRequires: gettext
BuildRequires: meson
BuildRequires: systemd-rpm-macros
BuildRequires: pkgconfig(flatpak) >= %{flatpak_version}
BuildRequires: pkgconfig(fuse3)
BuildRequires: pkgconfig(gdk-pixbuf-2.0)
BuildRequires: pkgconfig(gio-unix-2.0) >= %{glib_version}
BuildRequires: pkgconfig(gstreamer-pbutils-1.0)
BuildRequires: pkgconfig(json-glib-1.0)
BuildRequires: pkgconfig(libgeoclue-2.0) >= %{geoclue_version}
BuildRequires: pkgconfig(libpipewire-0.3) >= %{pipewire_version}
BuildRequires: pkgconfig(libsystemd)
BuildRequires: pkgconfig(umockdev-1.0)
BuildRequires: python3-dbusmock
BuildRequires: python3-gobject-base
BuildRequires: python3-pytest
%if %{undefined rhel}
BuildRequires: python3-pytest-xdist
%endif
%if %{with docs}
BuildRequires: python3-furo
BuildRequires: python3-sphinx-copybutton
BuildRequires: python3-sphinxext-opengraph
BuildRequires: /usr/bin/sphinx-build
%endif
BuildRequires: /usr/bin/gst-inspect-1.0
BuildRequires: gstreamer1-plugins-good
# for man-pages
BuildRequires: /usr/bin/rst2man

Requires:      dbus
Requires:      geoclue2 >= %{geoclue_version}
Requires:      glib2%{?_isa} >= %{glib_version}
Recommends:    pipewire >= %{pipewire_version}
Requires:      pipewire-libs%{?_isa} >= %{pipewire_version}
# Required for the document portal.
Requires:      fuse3

# https://github.com/containers/composefs/pull/229#issuecomment-1838735764
%if 0%{?rhel} >= 10
ExcludeArch:    %{ix86}
%endif

%description
xdg-desktop-portal works by exposing a series of D-Bus interfaces known as
portals under a well-known name (org.freedesktop.portal.Desktop) and object
path (/org/freedesktop/portal/desktop). The portal interfaces include APIs for
file access, opening URIs, printing and others.

%package  devel
Summary:  Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}

%description devel
The pkg-config file for %{name}.


%prep
%autosetup -p1


%build
mkdir -p redhat-linux-build
meson setup \
    --prefix=%{_prefix} \
    --libdir=%{_libdir} \
    --libexecdir=%{_libexecdir} \
    --bindir=%{_bindir} \
    --sbindir=%{_sbin} \
    --includedir=%{_includedir} \
    --datadir=%{_datadir} \
    --mandir=%{_mandir} \
    --infodir=%{_infodir} \
    --localedir=%{_datadir}/locale \
    --sysconfdir=%{_sysconfdir} \
    --localstatedir=%{_localstatedir} \
    --sharedstatedir=%{_sharedstatedir} \
    --wrap-mode=nodownload \
    --auto-features=enabled \
    --buildtype=plain \
    %{!?with_docs:-Ddocumentation=disabled} \
    redhat-linux-build

ninja -C redhat-linux-build %{?_smp_mflags} -v

%install
DESTDIR=%{buildroot} ninja -C redhat-linux-build install
install -dm 755 %{buildroot}/%{_pkgdocdir}
install -pm 644 README.md %{buildroot}/%{_pkgdocdir}
# This directory is used by implementations such as xdg-desktop-portal-gtk.
install -dm 755 %{buildroot}/%{_datadir}/xdg-desktop-portal/portals

%find_lang %{name}


%post
%systemd_user_post xdg-desktop-portal.service
%systemd_user_post xdg-document-portal.service
%systemd_user_post xdg-permission-store.service


%preun
%systemd_user_preun xdg-desktop-portal.service
%systemd_user_preun xdg-document-portal.service
%systemd_user_preun xdg-permission-store.service


%files -f %{name}.lang
%doc %{_pkgdocdir}
%license COPYING
%{_datadir}/dbus-1/interfaces/org.freedesktop.host.portal.Registry.xml
%{_datadir}/dbus-1/interfaces/org.freedesktop.portal.*.xml
%{_datadir}/dbus-1/interfaces/org.freedesktop.impl.portal.*.xml
%{_datadir}/dbus-1/services/org.freedesktop.portal.Desktop.service
%{_datadir}/dbus-1/services/org.freedesktop.portal.Documents.service
%{_datadir}/dbus-1/services/org.freedesktop.impl.portal.PermissionStore.service
%{_datadir}/xdg-desktop-portal/
%{_libexecdir}/xdg-desktop-portal
%{_libexecdir}/xdg-desktop-portal-rewrite-launchers
%{_libexecdir}/xdg-desktop-portal-validate-icon
%{_libexecdir}/xdg-desktop-portal-validate-sound
%{_libexecdir}/xdg-document-portal
%{_libexecdir}/xdg-permission-store
%{_mandir}/man5/portals.conf.5*
%{_userunitdir}/xdg-desktop-portal.service
%{_userunitdir}/xdg-desktop-portal-rewrite-launchers.service
%{_userunitdir}/xdg-document-portal.service
%{_userunitdir}/xdg-permission-store.service

%files devel
%{_datadir}/pkgconfig/xdg-desktop-portal.pc


%changelog
%autochangelog
