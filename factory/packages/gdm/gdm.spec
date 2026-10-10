%global _hardened_build 1

%define gtk3_version 2.99.2

%global major_version %%(echo %{version} | cut -d '.' -f1 | cut -d '~' -f1)
%global tarball_version %%(echo %{version} | tr '~' '.')

# This controls support for launching X11 desktops.
# gdm itself will always use Wayland.
%if 0%{?rhel}
%bcond x11 0
%else
%bcond x11 1
%endif

Name:           gdm
Epoch:          1
Version:        50.0
Release:        3%{?dist}
Summary:        The GNOME Display Manager

License:        GPL-2.0-or-later
URL:            https://wiki.gnome.org/Projects/GDM
Source0:        https://download.gnome.org/sources/gdm/%{major_version}/gdm-%{tarball_version}.tar.xz
Source1:        org.gnome.login-screen.gschema.override
Source2:        gdm.sysusers

# Downstream patches
Patch:          0001-Honor-initial-setup-being-disabled-by-distro-install.patch
Patch:          0001-data-add-system-dconf-databases-to-gdm-profile.patch
Patch:          0001-Add-headless-session-files.patch

BuildRequires:  dconf
BuildRequires:  desktop-file-utils
BuildRequires:  gcc
BuildRequires:  gettext-devel
BuildRequires:  git-core
BuildRequires:  meson
BuildRequires:  pam-devel
BuildRequires:  pkgconfig(accountsservice) >= 0.6.3
BuildRequires:  pkgconfig(audit)
BuildRequires:  pkgconfig(check)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(gtk+-3.0) >= %{gtk3_version}
BuildRequires:  pkgconfig(gudev-1.0)
BuildRequires:  pkgconfig(iso-codes)
BuildRequires:  pkgconfig(json-glib-1.0)
%if !0%{?rhel}
BuildRequires:  pkgconfig(libcanberra-gtk3)
%endif
BuildRequires:  pkgconfig(libkeyutils)
BuildRequires:  pkgconfig(libselinux)
BuildRequires:  pkgconfig(libsystemd)
BuildRequires:  pkgconfig(ply-boot-client)
BuildRequires:  pkgconfig(systemd)
BuildRequires:  pkgconfig(xau)
BuildRequires:  systemd-rpm-macros
BuildRequires:  which
BuildRequires:  yelp-tools

%if %{with x11}
BuildRequires:  pkgconfig(x11)
%endif

Provides: service(graphical-login) = %{name}

Requires: accountsservice
Requires: dbus-common
Requires: dconf
# since we use it, and pam spams the log if the module is missing
Requires: gnome-keyring-pam
Requires: gnome-session >= 50~alpha
Requires: gnome-session-wayland-session >= 50~alpha
Requires: gnome-settings-daemon >= 3.27.90
Requires: gnome-shell
Requires:       gnome50-el10-compat
Requires: iso-codes
# We need 1.0.4-5 since it lets us use "localhost" in auth cookies
Requires: libXau >= 1.0.4-4
Requires: pam
Requires: /sbin/nologin
Requires: systemd >= 186
Requires: system-logos
Requires: python3-pam

%if %{with x11}
Requires: xorg-x11-xinit
%endif

Provides: gdm-libs%{?_isa} = %{epoch}:%{version}-%{release}

%description
GDM, the GNOME Display Manager, handles authentication-related backend
functionality for logging in a user and unlocking the user's session after
it's been locked. GDM also provides functionality for initiating user-switching,
so more than one user can be logged in at the same time. It handles
graphical session registration with the system for both local and remote
sessions (in the latter case, via GNOME Remote Desktop and the RDP protocol).

%package devel
Summary: Development files for gdm
Requires: %{name}%{?_isa} = %{epoch}:%{version}-%{release}
Requires: gdm-pam-extensions-devel = %{epoch}:%{version}-%{release}

%description devel
The gdm-devel package contains headers and other
files needed to build custom greeters.

%package pam-extensions-devel
Summary: Macros for developing GDM extensions to PAM
Requires: pam-devel

%description pam-extensions-devel
The gdm-pam-extensions-devel package contains headers and other
files that are helpful to PAM modules wishing to support
GDM specific authentication features.

%prep
%autosetup -S git -p1 -n gdm-%{tarball_version}

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
    -Ddbus-sys=%{_datadir}/dbus-1/system.d \
    -Ddefault-path=/usr/local/bin:/usr/bin \
    -Ddefault-pam-config=redhat \
    -Ddistro=redhat \
%if %{with x11}
    -Dx11-support=true
%else
    -Dx11-support=false
%endif
ninja -C _build -j%{_smp_build_ncpus}

%install
DESTDIR=%{buildroot} ninja -C _build install

cp -a %{SOURCE1} %{buildroot}%{_datadir}/glib-2.0/schemas

install -p -m644 -D %{SOURCE2} %{buildroot}%{_sysusersdir}/%{name}.conf

mkdir -p %{buildroot}%{_sysconfdir}/dconf/db/gdm.d/locks

%if %{with x11}
ln -sf ../X11/xinit/Xsession %{buildroot}%{_sysconfdir}/gdm/
%endif

%find_lang gdm --with-gnome

%post
%systemd_post gdm.service

%preun
%systemd_preun gdm.service

%postun
%systemd_postun gdm.service

%files -f gdm.lang
%doc AUTHORS NEWS README.md
%license COPYING
%dir %{_sysconfdir}/gdm
%config(noreplace) %{_sysconfdir}/gdm/custom.conf
%config %{_sysconfdir}/pam.d/gdm-autologin
%config %{_sysconfdir}/pam.d/gdm-password
# not config files
%if %{with x11}
%{_sysconfdir}/gdm/Xsession
%endif
%{_datadir}/gdm/gdm.schemas
%{_datadir}/dbus-1/system.d/gdm.conf
%dir %{_sysconfdir}/dconf/db/gdm.d
%dir %{_sysconfdir}/dconf/db/gdm.d/locks
%{_datadir}/glib-2.0/schemas/org.gnome.login-screen.gschema.xml
%{_datadir}/glib-2.0/schemas/org.gnome.login-screen.gschema.override
%{_libexecdir}/gdm-runtime-config
%{_libexecdir}/gdm-session-worker
%{_libexecdir}/gdm-new-session
%{_libexecdir}/gdm-wayland-session
%if %{with x11}
%{_libexecdir}/gdm-x-session
%endif
%{_libexecdir}/gdm-headless-login-session
%{_sbindir}/gdm
%{_bindir}/gdm-config
%dir %{_datadir}/dconf
%dir %{_datadir}/dconf/profile
%{_datadir}/dconf/profile/gdm
%dir %{_datadir}/gdm/greeter
%dir %{_datadir}/gdm/greeter/applications
%dir %{_datadir}/gdm/greeter/wayland-sessions
%{_datadir}/gdm/greeter/applications/*
%{_datadir}/gdm/greeter/wayland-sessions/*
%{_datadir}/gdm/greeter-dconf-defaults
%{_datadir}/gdm/locale.alias
%{_datadir}/gdm/gdb-cmd
%{_datadir}/gnome-session/sessions/gnome-login.session
%{_datadir}/polkit-1/rules.d/20-gdm.rules
%{_datadir}/polkit-1/actions/org.gnome.displaymanager.policy
%{_libdir}/girepository-1.0/Gdm-1.0.typelib
%{_libdir}/security/pam_gdm.so
%{_libdir}/libgdm.so.1{,.*}
%{_libexecdir}/gdm-auth-config-redhat
%ghost %dir %{_localstatedir}/log/gdm
%ghost %dir %{_localstatedir}/lib/gdm
%ghost %dir %{_rundir}/gdm
%config %{_sysconfdir}/pam.d/gdm-smartcard
%config %{_sysconfdir}/pam.d/gdm-fingerprint
%config %{_sysconfdir}/pam.d/gdm-switchable-auth
%{_sysconfdir}/pam.d/gdm-launch-environment
%{_unitdir}/gdm.service
%{_unitdir}/gnome-headless-session@.service
%dir %{_userunitdir}/gnome-session@gnome-login.target.d/
%{_userunitdir}/gnome-session@gnome-login.target.d/gnome-login.session.conf
%{_sysusersdir}/%{name}.conf

%files devel
%dir %{_includedir}/gdm
%{_includedir}/gdm/*.h
%exclude %{_includedir}/gdm/gdm-pam-extensions.h
%exclude %{_includedir}/gdm/gdm-choice-list-pam-extension.h
%exclude %{_includedir}/gdm/gdm-custom-json-pam-extension.h
%exclude %{_includedir}/gdm/gdm-pam-extensions-common.h
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Gdm-1.0.gir
%{_libdir}/libgdm.so
%{_libdir}/pkgconfig/gdm.pc

%files pam-extensions-devel
%{_includedir}/gdm/gdm-pam-extensions.h
%{_includedir}/gdm/gdm-choice-list-pam-extension.h
%{_includedir}/gdm/gdm-custom-json-pam-extension.h
%{_includedir}/gdm/gdm-pam-extensions-common.h
%{_libdir}/pkgconfig/gdm-pam-extensions.pc

%changelog
* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-3
- Add explicit BuildRequires: gcc (COPR EL10 minimal buildroot does not
  pre-install gcc unlike Fedora; meson compiler detection fails without it)

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-2
- Replace %%meson/%%meson_build/%%meson_install with explicit meson/ninja
  to avoid "fg: no job control" on COPR builders (non-interactive bash).
- Remove %%autorelease/%%autochangelog: Fedora-specific macros not available on EL10.

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-1
- Update to 50.0 (GNOME 50 stable release)
- Track F44 branch instead of rawhide
- Drop gcc BuildRequires (pulled in transitively)
- Drop dbus-daemon Requires (covered by dbus-common)
- EL10: gate libcanberra-gtk3 BR behind %%if !0%%{?rhel} (no gtk3 on EL10)
- EL10: retain gnome50-el10-compat Requires (SELinux/PAM compat)
