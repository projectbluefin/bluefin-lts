%global nm_version 1.2
%global nma_version 1.0
%global glib_required_version 2.64
%global gtk_required_version 4.17
%global geoclue_version 2.6.0
%global gnome_desktop_version 44.0-7

%global tarball_version 50.0
%global major_version 50

%if 0%{?rhel}
%bcond_with webkitgtk
%else
%bcond_without webkitgtk
%endif

Name:           gnome-initial-setup
Version:        50.0
Release:        5%{?dist}
Summary:        Bootstrapping your OS

License:        GPL-2.0-or-later
URL:            https://wiki.gnome.org/Design/OS/InitialSetup
Source0:        https://download.gnome.org/sources/%{name}/%{major_version}/%{name}-%{tarball_version}.tar.xz

BuildRequires:  desktop-file-utils
BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  pkgconfig(accountsservice)
BuildRequires:  pkgconfig(fontconfig)
BuildRequires:  pkgconfig(gdm)
BuildRequires:  pkgconfig(geocode-glib-2.0)
BuildRequires:  pkgconfig(gio-2.0) >= %{glib_required_version}
BuildRequires:  pkgconfig(gio-unix-2.0) >= %{glib_required_version}
BuildRequires:  pkgconfig(glib-2.0) >= %{glib_required_version}
BuildRequires:  pkgconfig(gnome-desktop-4)
BuildRequires:  pkgconfig(gsettings-desktop-schemas)
BuildRequires:  pkgconfig(gstreamer-1.0)
BuildRequires:  pkgconfig(gtk4) >= %{gtk_required_version}
BuildRequires:  pkgconfig(gweather4)
BuildRequires:  pkgconfig(ibus-1.0)
BuildRequires:  pkgconfig(iso-codes)
BuildRequires:  pkgconfig(json-glib-1.0)
BuildRequires:  pkgconfig(krb5)
BuildRequires:  pkgconfig(libadwaita-1)
BuildRequires:  pkgconfig(libgeoclue-2.0) >= %{geoclue_version}
BuildRequires:  pkgconfig(libnma-gtk4) >= %{nma_version}
BuildRequires:  pkgconfig(libnm) >= %{nm_version}
BuildRequires:  pkgconfig(libsecret-1)
BuildRequires:  pkgconfig(pango)
BuildRequires:  pkgconfig(polkit-gobject-1)
BuildRequires:  pkgconfig(pwquality)
BuildRequires:  pkgconfig(rest-1.0)
BuildRequires:  pkgconfig(malcontent-0)
BuildRequires:  pkgconfig(malcontent-ui-1)
%if %{with webkitgtk}
BuildRequires:  pkgconfig(webkitgtk-6.0)
%endif

# gnome-initial-setup is being run by gdm
Requires: gdm
Requires: geoclue2-libs%{?_isa} >= %{geoclue_version}
Requires: glib2%{?_isa} >= %{glib_required_version}
Requires: gnome-desktop4%{?_isa} >= %{gnome_desktop_version}
# we install a rules file
Requires: polkit-js-engine
Requires: /usr/bin/tecla

Requires(pre): shadow-utils

Provides: user(%name)

# https://fedoraproject.org/wiki/Changes/EncourageI686LeafRemoval
ExcludeArch: %{ix86}

%description
GNOME Initial Setup is an alternative to firstboot, providing
a good setup experience to welcome you to your system, and walks
you through configuring it. It is integrated with gdm.

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
    --wrap-mode=nodownload \
    -Dparental_controls=enabled \
%if !%{with webkitgtk}
    -Dwebkitgtk=disabled \
%endif
    %{nil}
ninja -C _build -j%{_smp_build_ncpus}

%install
DESTDIR=%{buildroot} ninja -C _build install

mkdir -p %{buildroot}%{_datadir}/gnome-initial-setup

%find_lang %{name}

%pre
# we do not use sysusers yet because we need /var/lib/gnome-initial-setup
# to be owned by the gnome-initial-setup user. please do not convert
# to sysusers without making sure this is handled, maybe by tmpfiles
useradd -rM -d /run/gnome-initial-setup/ -s /sbin/nologin %{name} &>/dev/null || :

%files -f %{name}.lang
%license COPYING
%doc NEWS README.md
%{_libexecdir}/gnome-initial-setup
%{_libexecdir}/gnome-initial-setup-copy-worker
%{_datadir}/applications/gnome-initial-setup.desktop
%{_datadir}/dconf/profile/gnome-initial-setup
%dir %{_datadir}/gnome-initial-setup
%{_datadir}/gnome-initial-setup/initial-setup-dconf-defaults
%{_datadir}/gnome-session/sessions/gnome-initial-setup.session
%{_datadir}/gnome-shell/modes/initial-setup.json
%{_datadir}/polkit-1/rules.d/20-gnome-initial-setup.rules
%{_sysusersdir}/gnome-initial-setup.conf
%{_userunitdir}/*

%changelog
* Mon Mar 30 2026 James Reilly <jreilly1821@gmail.com> - 50.0-5
- Re-enable parental controls (-Dparental_controls=enabled)
- Add BuildRequires: pkgconfig(malcontent-0), pkgconfig(malcontent-ui-1)
- flatpak-devel and appstream-devel now available from our COPR
- malcontent 0.14.0 now built in COPR

* Mon Mar 30 2026 James Reilly <jreilly1821@gmail.com> - 50.0-4
- Revert parental_controls=enabled: flatpak-devel and appstream-devel not
  available in EL10/EPEL 10 (needed by libmalcontent-ui). Track in TODO.

* Mon Mar 30 2026 James Reilly <jreilly1821@gmail.com> - 50.0-3
- Enable parental controls (-Dparental_controls=enabled); malcontent and
  libglib-testing are now available in the COPR
- Add BuildRequires: malcontent-0, malcontent-ui-1

* Mon Mar 30 2026 James Reilly <jreilly1821@gmail.com> - 50.0-2
- Replace %%meson/%%meson_build/%%meson_install with explicit meson/ninja
  to avoid "fg: no job control" on COPR builders (non-interactive bash)

* Mon Mar 30 2026 James Reilly <jreilly1821@gmail.com> - 50.0-1
- Update to 50.0 for GNOME 50 on EL10
- Track F44 branch; webkitgtk disabled for RHEL builds
- Replace %%autorelease/%%autochangelog with manual macros (EL10 compat)
