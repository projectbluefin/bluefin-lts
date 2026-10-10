%bcond cloudproviders %{undefined rhel}

%global glib2_version 2.79.0
%global gnome_autoar_version 0.4.4
%global gtk4_version 4.17.5
%global libadwaita_version 1.6~beta

Name:           nautilus
Version:        50.0

%global tarball_version %%(echo %{version} | tr '~' '.')
%global major_version %%(cut -d "." -f 1 <<<%{tarball_version})

Release:        4%{?dist}
Summary:        File manager for GNOME

# Sources are GPL-3.0-or-later and Appdata is CC0-1.0.
License:        GPL-3.0-or-later AND CC0-1.0
URL:            https://apps.gnome.org/Nautilus/
Source0:        https://download.gnome.org/sources/%{name}/%{major_version}/%{name}-%{tarball_version}.tar.xz
# https://pagure.io/fedora-workstation/issue/442
Patch:          default-terminal.patch

BuildRequires:  desktop-file-utils
BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  pkgconfig(gexiv2-0.16)
BuildRequires:  pkgconfig(gi-docgen)
BuildRequires:  pkgconfig(glib-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(gnome-autoar-0) >= %{gnome_autoar_version}
BuildRequires:  pkgconfig(gnome-desktop-4)
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(gsettings-desktop-schemas)
BuildRequires:  pkgconfig(gstreamer-pbutils-1.0)
BuildRequires:  pkgconfig(gstreamer-tag-1.0)
BuildRequires:  pkgconfig(gtk4) >= %{gtk4_version}
BuildRequires:  pkgconfig(libadwaita-1) >= %{libadwaita_version}
%if %{with cloudproviders}
BuildRequires:  pkgconfig(cloudproviders)
%endif
BuildRequires:  pkgconfig(libportal)
BuildRequires:  pkgconfig(libportal-gtk4)
BuildRequires:  pkgconfig(libseccomp)
BuildRequires:  pkgconfig(libselinux)
BuildRequires:  pkgconfig(libxml-2.0)
BuildRequires:  pkgconfig(tracker-sparql-3.0)
BuildRequires:  pkgconfig(x11)
BuildRequires:  /usr/bin/appstream-util
# needed by test/automated/displayless
BuildRequires:  localsearch
BuildRequires:  pkgconfig(glycin-gtk4-2)
BuildRequires:  pkgconfig(blueprint-compiler)

Requires:       glib2%{_isa} >= %{glib2_version}
Requires:       gnome-autoar%{_isa} >= %{gnome_autoar_version}
Requires:       gsettings-desktop-schemas%{_isa}
Requires:       gtk4%{_isa} >= %{gtk4_version}
Requires:       gvfs%{_isa}
%if ! 0%{?flatpak}
Recommends:     gvfs-fuse%{_isa}
%endif
Requires:       libadwaita%{_isa} >= %{libadwaita_version}
# the main binary links against libnautilus-extension.so
# don't depend on soname, rather on exact version
Requires:       %{name}-extensions%{_isa} = %{version}-%{release}
# For the org.freedesktop.Tracker3.Miner.Files GSettings schema
Requires:       localsearch

Recommends:     glycin-thumbnailer%{_isa}
Recommends:     gst-thumbnailers%{_isa}

Provides:       bundled(libgd)

%description
Nautilus is the file manager and graphical shell for the GNOME desktop
that makes it easy to manage your files and the rest of your system.
It allows to browse directories on local and remote filesystems, preview
files and launch applications associated with them.
It is also responsible for handling the icons on the GNOME desktop.

%package extensions
Summary:        Nautilus extensions library
License:        LGPL-2.1-or-later

%description extensions
This package provides the libraries used by nautilus extensions.

%package devel
Summary:        Support for developing nautilus extensions
License:        LGPL-2.1-or-later
Requires:       %{name}%{_isa} = %{version}-%{release}
Requires:       %{name}-extensions%{_isa} = %{version}-%{release}
# Because web fonts from upstream are not bundled in the gi-docgen package,
# packages containing documentation generated with gi-docgen should depend on
# this metapackage to ensure the proper system fonts are present.
Recommends:     gi-docgen-fonts

%description devel
This package provides libraries and header files needed
for developing nautilus extensions.

%prep
%autosetup -p1 -n %{name}-%{tarball_version}

# Remove -Werror from compiler flags
sed -i '/-Werror/d' meson.build

%build
meson setup --prefix=/usr --libdir=%{_libdir} --buildtype=plain build \
  -Ddocs=true \
  -Dextensions=true \
  -Dintrospection=true \
  -Dselinux=true \
  -Dcloudproviders=%{?with_cloudproviders:true}%{?!with_cloudproviders:false}
meson compile -C build

%install
DESTDIR=%{buildroot} meson install -C build

%find_lang %{name}

%check
appstream-util validate-relax --nonet $RPM_BUILD_ROOT%{_metainfodir}/org.gnome.Nautilus.metainfo.xml
desktop-file-validate $RPM_BUILD_ROOT%{_datadir}/applications/*.desktop

%files  -f %{name}.lang
%doc NEWS README.md
%license LICENSE
%{_datadir}/applications/*
%{_bindir}/*
%{_datadir}/dbus-1/services/org.freedesktop.FileManager1.service
%{_datadir}/dbus-1/services/org.gnome.Nautilus.service
%dir %{_datadir}/gnome-shell
%dir %{_datadir}/gnome-shell/search-providers
%{_datadir}/gnome-shell/search-providers/org.gnome.Nautilus.search-provider.ini
%{_datadir}/icons/hicolor/scalable/apps/org.gnome.Nautilus.svg
%{_datadir}/icons/hicolor/symbolic/apps/org.gnome.Nautilus-symbolic.svg

%{_datadir}/glib-2.0/schemas/org.gnome.nautilus.gschema.xml
%{_datadir}/nautilus/
%{_libdir}/nautilus/extensions-4/libnautilus-image-properties.so
%{_libdir}/nautilus/extensions-4/libtotem-properties-page.so
%{_metainfodir}/org.gnome.Nautilus.metainfo.xml
%{_mandir}/man1/nautilus.1*
%{_mandir}/man1/nautilus-autorun-software.1*

%files extensions
%license libnautilus-extension/LICENSE
%{_libdir}/libnautilus-extension.so.4*
%{_libdir}/girepository-1.0/Nautilus-4.1.typelib
%dir %{_libdir}/nautilus
%dir %{_libdir}/nautilus/extensions-4

%files devel
%{_includedir}/nautilus
%{_libdir}/pkgconfig/libnautilus-extension-4.pc
%{_libdir}/libnautilus-extension.so
%{_datadir}/gir-1.0/Nautilus-4.1.gir
%doc %{_datadir}/doc/nautilus/

%changelog
* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-4
- Add explicit -Ddocs=true (docs option defaults to disabled, not auto-detect)

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-3
- Enable docs (gi-docgen is now available in COPR); restore unconditional man pages

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-2
- EL10: gate man pages behind %%if !0%%{?rhel} (-Ddocs=false also disables man page generation)

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 50.0-1
- Update to 50.0 (GNOME 50 stable release)
- Track F44 branch instead of rawhide
- Add man pages to %%files
- Properly wire %%bcond cloudproviders into meson -Dcloudproviders= argument
- EL10: keep -Ddocs=false (gi-docgen not available on EL10)
- Remove %%autorelease/%%autochangelog: Fedora-specific macros not available on EL10.
