%global debug_package %{nil}

%global tarball_version %%(echo %{version} | tr '~' '.')

Name:           gsettings-desktop-schemas
Version:        50.0
Release:        2%{?dist}
Summary:        A collection of GSettings schemas

License:        LGPL-2.1-or-later
# no homepage exists for this component
URL:            https://gitlab.gnome.org/GNOME/gsettings-desktop-schemas
Source0:        https://download.gnome.org/sources/%{name}/50/%{name}-%{tarball_version}.tar.xz
Source1:        org.gnome.desktop.interface.rhel.gschema.override

BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  glib2-devel >= 2.31.0
BuildRequires:  gobject-introspection-devel
BuildRequires:  meson

Requires: glib2 >= 2.31.0

# Recommend the default fonts set in the schemas
%if 0%{?rhel} && 0%{?rhel} >= 10
Recommends: font(redhattextvf)
Recommends: font(redhatmonovf)
%else
Recommends: font(adwaitasans)
Recommends: font(adwaitamono)
%endif

%description
gsettings-desktop-schemas contains a collection of GSettings schemas for
settings shared by various components of a desktop.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries
and header files for developing applications that use %{name}.


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
    -Dintrospection=true
ninja -C _build -j%{_smp_build_ncpus}

%install
DESTDIR=%{buildroot} ninja -C _build install

%if 0%{?rhel} && 0%{?rhel} >= 10
cp %{SOURCE1} $RPM_BUILD_ROOT%{_datadir}/glib-2.0/schemas
%endif

%find_lang %{name} --with-gnome


%check
# Test that the schemas compile
glib-compile-schemas --dry-run --strict %{buildroot}%{_datadir}/glib-2.0/schemas


%files -f %{name}.lang
%doc AUTHORS MAINTAINERS NEWS README
%license COPYING
%{_datadir}/glib-2.0/schemas/*
%dir %{_datadir}/GConf
%dir %{_datadir}/GConf/gsettings
%{_datadir}/GConf/gsettings/gsettings-desktop-schemas.convert
%{_datadir}/GConf/gsettings/wm-schemas.convert
%{_libdir}/girepository-1.0/GDesktopEnums-3.0.typelib

%files devel
%doc HACKING
%{_includedir}/*
%{_datadir}/pkgconfig/*
%{_datadir}/gir-1.0/GDesktopEnums-3.0.gir


%changelog
* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-2
- Add gcc BuildRequires: meson checks for a C compiler at configure time even
  for schema-only projects; gcc is not auto-installed in EL10 COPR buildroots.
- Replace %%meson/%%meson_build/%%meson_install with explicit meson/ninja to
  avoid "fg: no job control" failure on COPR builders.
- Remove %%autochangelog: Fedora-specific macro not available on EL10.

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-1
- Update to 50.0 (GNOME 50 stable release)
- Track F44 branch instead of rawhide
- Drop gcc BuildRequires (pulled in transitively)
- Adopt %meson build macros
