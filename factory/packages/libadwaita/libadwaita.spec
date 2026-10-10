%global apiver  1
%global gtk_version 4.17.5
%global glib_version 2.80.0

%global tarball_version %%(echo %{version} | tr '~' '.')

Name:           libadwaita
Version:        1.9.0
Release:        2%{?dist}
Summary:        Building blocks for modern GNOME applications

# part of src/adw-spring-animation.c is MIT
License:        LGPL-2.1-or-later AND MIT
URL:            https://gitlab.gnome.org/GNOME/libadwaita
Source0:        https://download.gnome.org/sources/%{name}/1.9/%{name}-%{tarball_version}.tar.xz

BuildRequires:  desktop-file-utils
BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  gi-docgen
BuildRequires:  libappstream-glib
BuildRequires:  meson >= 0.63.0
BuildRequires:  vala
BuildRequires:  /usr/bin/sassc
BuildRequires:  pkgconfig(appstream)
BuildRequires:  pkgconfig(fribidi)
BuildRequires:  pkgconfig(glib-2.0) >= %{glib_version}
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(gtk4) >= %{gtk_version}

Requires:       gtk4%{?_isa} >= %{gtk_version}

%description
Building blocks for modern GNOME applications.


%package        devel
Summary:        Development files for %{name}

Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       vala
Recommends:     %{name}-doc = %{version}-%{release}
Suggests:       %{name}-demo = %{version}-%{release}

%description    devel
Development files for %{name}.


%package        doc
Summary:        Documentation files for %{name}
BuildArch:      noarch

Recommends:     %{name}-devel = %{version}-%{release}
# Because web fonts from upstream are not bundled in the gi-docgen package,
# packages containing documentation generated with gi-docgen should depend on
# this metapackage to ensure the proper system fonts are present.
Recommends:     gi-docgen-fonts

%description    doc
Documentation files for %{name}.


%package        demo
Summary:        Demo files for %{name}
BuildArch:      noarch

Requires:       %{name} = %{version}-%{release}
Suggests:       %{name}-devel = %{version}-%{release}

%description    demo
Demo files for %{name}.


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
    -Ddocumentation=true
ninja -C _build -j%{_smp_build_ncpus}


%install
DESTDIR=%{buildroot} ninja -C _build install
%find_lang %{name}


%check
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/*.xml
desktop-file-validate %{buildroot}%{_datadir}/applications/*.desktop


%files -f %{name}.lang
%license COPYING
%doc README.md AUTHORS NEWS
%{_bindir}/adwaita-%{apiver}-demo
%{_libdir}/%{name}-%{apiver}.so.0
%{_libdir}/girepository-1.0/*.typelib

%files devel
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/*-%{apiver}.gir
%{_datadir}/vala/vapi/%{name}-%{apiver}.*
%{_includedir}/%{name}-%{apiver}/
%{_libdir}/%{name}-%{apiver}.so
%{_libdir}/pkgconfig/*-%{apiver}.pc

%files doc
%{_docdir}/%{name}-%{apiver}/

%files demo
%{_datadir}/applications/*.desktop
%{_datadir}/icons/hicolor/*/apps/*.svg
%{_metainfodir}/*.metainfo.xml


%changelog
* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 1.9.0-2
- Replace %%meson/%%meson_build/%%meson_install with explicit meson/ninja
  to avoid "fg: no job control" on COPR builders (non-interactive bash).
- Remove %%autochangelog: Fedora-specific macro not available on EL10.

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 1.9.0-1
- Update to 1.9.0 (libadwaita stable release for GNOME 50)
- Track F44 branch instead of rawhide
