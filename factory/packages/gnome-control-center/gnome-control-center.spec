%global blueprint_compiler_version 0.17
%global gcr_version 4.1.0
%global gnome_online_accounts_version 3.51.0
%global glib2_version 2.76.6
%global gnome_desktop_version 44.0-7
%global gsd_version 48~rc
%global gsettings_desktop_schemas_version 48~alpha-2
%global upower_version 1.90.6
%global gtk4_version 4.15.2
%global gnome_bluetooth_version 42~alpha
%global libadwaita_version 1.8~alpha
%global nm_version 1.52.0

%global tarball_version %%(echo %{version} | tr '~' '.')

# Disable parental control for RHEL builds
%bcond malcontent %[!0%{?rhel}]

Name:           gnome-control-center
Version:        50.0
Release:        4%{?dist}
Summary:        Utilities to configure the GNOME desktop

License:        GPL-2.0-or-later AND CC0-1.0
URL:            https://gitlab.gnome.org/GNOME/gnome-control-center/
Source0:        https://download.gnome.org/sources/%{name}/50/%{name}-%{tarball_version}.tar.xz

BuildRequires:  blueprint-compiler >= %{blueprint_compiler_version}
BuildRequires:  desktop-file-utils
BuildRequires:  docbook-style-xsl libxslt
BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  pkgconfig(accountsservice)
BuildRequires:  pkgconfig(colord)
BuildRequires:  pkgconfig(colord-gtk4)
BuildRequires:  pkgconfig(tecla)
BuildRequires:  pkgconfig(cups)
BuildRequires:  pkgconfig(gcr-4) >= %{gcr_version}
BuildRequires:  pkgconfig(gdk-pixbuf-2.0)
# gdk-wayland-3.0 is gtk3; not available on EL10
%if !0%{?rhel}
BuildRequires:  pkgconfig(gdk-wayland-3.0)
%endif
BuildRequires:  pkgconfig(gio-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(gnome-desktop-4) >= %{gnome_desktop_version}
BuildRequires:  pkgconfig(gnome-settings-daemon) >= %{gsd_version}
BuildRequires:  pkgconfig(goa-1.0) >= %{gnome_online_accounts_version}
BuildRequires:  pkgconfig(goa-backend-1.0)
BuildRequires:  pkgconfig(gsettings-desktop-schemas) >= %{gsettings_desktop_schemas_version}
BuildRequires:  pkgconfig(gsound)
BuildRequires:  pkgconfig(gtk4) >= %{gtk4_version}
BuildRequires:  pkgconfig(gudev-1.0)
BuildRequires:  pkgconfig(ibus-1.0)
BuildRequires:  pkgconfig(libadwaita-1) >= %{libadwaita_version}
BuildRequires:  pkgconfig(libgtop-2.0)
BuildRequires:  pkgconfig(libnm) >= %{nm_version}
BuildRequires:  pkgconfig(libnma-gtk4)
BuildRequires:  pkgconfig(libpulse)
BuildRequires:  pkgconfig(libpulse-mainloop-glib)
BuildRequires:  pkgconfig(libsecret-1)
BuildRequires:  pkgconfig(libsoup-3.0)
BuildRequires:  pkgconfig(libxml-2.0)
%if %{with malcontent}
BuildRequires:  pkgconfig(malcontent-0)
%endif
BuildRequires:  pkgconfig(mm-glib)
BuildRequires:  pkgconfig(polkit-gobject-1)
BuildRequires:  pkgconfig(pwquality)
BuildRequires:  pkgconfig(smbclient)
BuildRequires:  pkgconfig(udisks2)
BuildRequires:  pkgconfig(upower-glib) >= %{upower_version}
BuildRequires:  pkgconfig(x11)
BuildRequires:  pkgconfig(xi)
%ifnarch s390 s390x
BuildRequires:  pkgconfig(gnome-bluetooth-3.0) >= %{gnome_bluetooth_version}
BuildRequires:  pkgconfig(libwacom)
%endif

# Versioned library deps
Requires: libadwaita%{?_isa} >= %{libadwaita_version}
Requires: glib2%{?_isa} >= %{glib2_version}
Requires: gnome-desktop4%{?_isa} >= %{gnome_desktop_version}
Requires: gnome-online-accounts%{?_isa} >= %{gnome_online_accounts_version}
Requires: gnome-settings-daemon%{?_isa} >= %{gsd_version}
Requires: gsettings-desktop-schemas%{?_isa} >= %{gsettings_desktop_schemas_version}
Requires: gtk4%{?_isa} >= %{gtk4_version}
Requires: upower%{?_isa} >= %{upower_version}
%ifnarch s390 s390x
Recommends: gnome-bluetooth%{?_isa} >= 1:%{gnome_bluetooth_version}
%endif

Requires: %{name}-filesystem = %{version}-%{release}
# For user accounts
Requires: accountsservice
Requires: alsa-lib
# For the thunderbolt panel
Recommends: bolt
# For the color panel
Requires: colord
# For the printers panel
Requires: cups-pk-helper
Requires: dbus
# For the user languages
Requires: iso-codes
%if %{with malcontent}
# For parental controls support
Requires: malcontent
Recommends: malcontent-control
%endif
# For the network panel
Recommends: NetworkManager-wifi
Recommends: nm-connection-editor
# For Show Details in the color panel
Recommends: gnome-color-manager
# For the sharing panel
Recommends: gnome-remote-desktop
%if 0%{?fedora}
Recommends: rygel
%endif
# For the info/details panel
Recommends: switcheroo-control
# For the keyboard panel
Requires: /usr/bin/tecla
%if 0%{?fedora} >= 35 || 0%{?rhel} >= 9
# For the power panel
Recommends: ppd-service
%if 0%{?fedora} && 0%{?fedora} < 41
Suggests: power-profiles-daemon
%else
Suggests: tuned-ppd
%endif
%endif

# Renamed in F28
Provides: control-center = 1:%{version}-%{release}
Provides: control-center%{?_isa} = 1:%{version}-%{release}
Obsoletes: control-center < 1:%{version}-%{release}

%description
This package contains configuration utilities for the GNOME desktop, which
allow to configure accessibility options, desktop fonts, keyboard and mouse
properties, sound setup, desktop theme and background, user interface
properties, screen resolution, and other settings.

%package filesystem
Summary: GNOME Control Center directories
# NOTE: this is an "inverse dep" subpackage. It gets pulled in
# NOTE: by the main package and MUST not depend on the main package
BuildArch: noarch
# Renamed in F28
Provides: control-center-filesystem = 1:%{version}-%{release}
Obsoletes: control-center-filesystem < 1:%{version}-%{release}

%description filesystem
The GNOME control-center provides a number of extension points
for applications. This package contains directories where applications
can install configuration files that are picked up by the control-center
utilities.

%prep
%autosetup -p1 -n %{name}-%{tarball_version}

%build
export PKG_CONFIG_PATH=/usr/share/pkgconfig:/usr/lib64/pkgconfig
meson setup --prefix=/usr --libdir=%{_libdir} --buildtype=plain --wrap-mode=nodownload build \
  -Ddocumentation=false \
  -Dlocation-services=enabled \
  -Ddistributor_logo=%{_datadir}/pixmaps/fedora-logo.png \
  -Ddark_mode_distributor_logo=%{_datadir}/pixmaps/system-logo-white.png \
  -Dmalcontent=false \
  %{nil}
meson compile -C build

%install
DESTDIR=%{buildroot} meson install -C build

# We do want this
mkdir -p $RPM_BUILD_ROOT%{_datadir}/gnome/wm-properties

# We don't want these
rm -rf $RPM_BUILD_ROOT%{_datadir}/gnome/autostart
rm -rf $RPM_BUILD_ROOT%{_datadir}/gnome/cursor-fonts

%find_lang %{name} --all-name --with-gnome

%check
# desktop-file-validate %{buildroot}%{_datadir}/applications/org.gnome.Shell.Extensions.desktop

%files -f %{name}.lang
%license COPYING
%doc NEWS README.md
%{_bindir}/gnome-control-center
%{_datadir}/applications/*.desktop
%{_datadir}/bash-completion/completions/gnome-control-center
%{_datadir}/dbus-1/services/org.gnome.Settings.SearchProvider.service
%{_datadir}/dbus-1/services/org.gnome.Settings.service
%{_datadir}/dbus-1/services/org.gnome.Settings.GlobalShortcutsProvider.service
%{_datadir}/dbus-1/interfaces/org.gnome.GlobalShortcutsRebind.xml
%{_datadir}/gettext/
%{_datadir}/glib-2.0/schemas/org.gnome.Settings.gschema.xml
%{_datadir}/gnome-control-center/keybindings/*.xml
%{_datadir}/gnome-control-center/pixmaps
%{_datadir}/gnome-shell/search-providers/org.gnome.Settings.search-provider.ini
%{_datadir}/icons/gnome-logo-text*.svg
%{_datadir}/icons/hicolor/*/*/*
%if !0%{?rhel}
%{_mandir}/man1/gnome-control-center.1*
%endif
%{_metainfodir}/org.gnome.Settings.metainfo.xml
%{_datadir}/pixmaps/faces
%{_datadir}/pkgconfig/gnome-keybindings.pc
%{_datadir}/polkit-1/actions/org.gnome.controlcenter.*.policy
%{_datadir}/polkit-1/rules.d/gnome-control-center.rules
%{_datadir}/sounds/gnome/default/*/*.ogg
%{_libexecdir}/gnome-control-center-search-provider
%{_libexecdir}/gnome-control-center-print-renderer
%{_libexecdir}/gnome-control-center-global-shortcuts-provider

%files filesystem
%dir %{_datadir}/gnome-control-center
%dir %{_datadir}/gnome-control-center/keybindings
%dir %{_datadir}/gnome/wm-properties

%changelog
* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-4
- Restore -Ddocumentation=false: gcc docs need yelp-tools/itstool not currently
  wired in; gate man page behind %%if !0%%{?rhel} to avoid packaging missing file

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-3
- Enable documentation (drop -Ddocumentation=false); gnome-control-center uses
  docbook/xslt for man pages which are already in BuildRequires

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-2
- EL10: gate man page behind %%if !0%%{?rhel} (-Ddocumentation=false disables man pages)

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-1
- Update to 50.0 (GNOME 50 stable release)
- Track F44 branch instead of rawhide
- Drop libcanberra BuildRequires (removed upstream in 50.0)
- Drop epoxy BuildRequires (removed upstream in 50.0)
- Drop version floor on tecla BR (aligned with F44)
- Add manpage to %%files
- Add ppd-service Recommends block (gated on rhel >= 9, aligns with F44)
- EL10: retain gdk-wayland-3.0 guard (no gtk3 on EL10)
- EL10: retain manual meson setup with PKG_CONFIG_PATH and -Ddocumentation=false

* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 50~rc-10
- Revert hacks and use real tecla >= 47.0 dependency
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 50~rc-9
- Revert tecla hacks and use pkgconfig(tecla) provided by libcanberra-devel
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 50~rc-8
- Brute-force skip tecla check in panels/keyboard/meson.build
- Re-add epoxy build dependency
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 50~rc-2
- EL10: gate gdk-wayland-3.0 (gtk3) and gsound (pulls libcanberra→gtk3)
  BuildRequires behind %if !0%?rhel
