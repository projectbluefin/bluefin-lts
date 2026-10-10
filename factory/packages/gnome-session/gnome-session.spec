%global major_version 50
%global tarball_version 50.0
%define po_package gnome-session

Name:           gnome-session
Version:        50.0
Release:        3%{?dist}
Summary:        GNOME session manager

License:        GPL-2.0-or-later
URL:            https://gitlab.gnome.org/GNOME/gnome-session
Source:         https://download.gnome.org/sources/gnome-session/%{major_version}/%{name}-%{tarball_version}.tar.xz

# For https://fedoraproject.org/w/index.php?title=Changes/HiddenGrubMenu
# This should go upstream once systemd has a generic interface for this
Patch:          0001-Fedora-Set-grub-boot-flags-on-shutdown-reboot.patch

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  pkgconfig(gnome-desktop-4)
BuildRequires:  pkgconfig(libsystemd)
BuildRequires:  pkgconfig(systemd)

BuildRequires:  gettext
BuildRequires:  xmlto
BuildRequires:  /usr/bin/xsltproc

# an artificial requires to make sure we get dconf, for now
Requires: dconf

Requires: gsettings-desktop-schemas >= 0.1.7

Requires: dbus

Obsoletes: gnome-session < 50.0
Conflicts: gnome-desktop3 < 44.4-2
Conflicts: shared-mime-info < 2.0-4
Requires: shared-mime-info

# https://github.com/containers/composefs/pull/229#issuecomment-1838735764
%if 0%{?rhel} >= 10
ExcludeArch:    %{ix86}
%endif


%description
gnome-session manages a GNOME desktop or GDM login session. It starts up
the other core GNOME components and handles logout and saving the session.

%package wayland-session
Summary: Desktop file for wayland based gnome session
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: xorg-x11-server-Xwayland%{?_isa} >= 1.20.99.1
Requires: gnome-shell
Obsoletes: gnome-session-xsession < %{version}-%{release}

%description wayland-session
Desktop file to add GNOME on wayland to display manager session menu.

%prep
%autosetup -p1 -n %{name}-%{tarball_version}

%build
meson setup _build \
    --buildtype=plain \
    --prefix=%{_prefix} \
    --libdir=%{_libdir} \
    --libexecdir=%{_libexecdir} \
    --bindir=%{_bindir} \
    --sbindir=%{_sbindir} \
    --includedir=%{_includedir} \
    --datadir=%{_datadir} \
    --mandir=%{_mandir} \
    --infodir=%{_infodir} \
    --localedir=%{_datadir}/locale \
    --sysconfdir=%{_sysconfdir} \
    --localstatedir=%{_localstatedir} \
    --sharedstatedir=%{_sharedstatedir} \
    --wrap-mode=nodownload
ninja -C _build -j%{_smp_build_ncpus}

%install
DESTDIR=%{buildroot} ninja -C _build install

%find_lang %{po_package}

%ldconfig_scriptlets

%files wayland-session
%{_datadir}/wayland-sessions/*

%files -f %{po_package}.lang
%doc NEWS
%license COPYING
%{_bindir}/gnome-session*
%{_libexecdir}/gnome-session-ctl
%{_libexecdir}/gnome-session-init-worker
%{_libexecdir}/gnome-session-service
%{_mandir}/man1/gnome-session*1.*
%{_datadir}/applications/gnome-mimeapps.list
%{_datadir}/gnome-session/
%dir %{_datadir}/xdg-desktop-portal
%{_datadir}/xdg-desktop-portal/gnome-portals.conf
%{_datadir}/doc/gnome-session/html
%{_datadir}/glib-2.0/schemas/org.gnome.SessionManager.gschema.xml
%{_userunitdir}/gnome-session*
%{_userunitdir}/app-flatpak-.scope.d/override.conf
%{_userunitdir}/app-gnome-.scope.d/override.conf

%changelog
* Mon Mar 30 2026 James Reilly <jreilly1821@gmail.com> - 50.0-3
- Add Obsoletes: gnome-session < 50.0 to ensure EL10's stock gnome-session
  46.0 is replaced; without this the old gnome-session-init-worker binary
  (which references the removed org.gnome.Shell.target) could remain on
  disk alongside GNOME 50 packages (tuna-os/tunaOS#80)

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-2
- Replace %%meson/%%meson_build/%%meson_install with explicit meson/ninja
  to avoid "fg: no job control" on COPR builders (non-interactive bash).
- Remove %%autochangelog: Fedora-specific macro not available on EL10.

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-1
- Update to 50.0 (GNOME 50 stable release)
- Track F44 branch instead of rawhide
