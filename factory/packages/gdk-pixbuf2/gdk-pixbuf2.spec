%global glib2_version 2.56.0
%global glycin_version 2.0.1

# Normally we want auto features enabled to ensure no important feature gets
# disabled by mistake. But in this package, the auto features are mostly legacy
# or unwanted, and we should manually enable only what we want.

Name:           gdk-pixbuf2
Version:        2.44.5
Release:        4%{?dist}
Summary:        An image loading library

License:        LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/GNOME/gdk-pixbuf
Source0:        https://download.gnome.org/sources/gdk-pixbuf/2.44/gdk-pixbuf-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  gettext
BuildRequires:  pkgconfig(gio-2.0) >= %{glib2_version}
BuildRequires:  pkgconfig(glycin-2) >= %{glycin_version}
BuildRequires:  meson
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  shared-mime-info

Requires: glib2%{?_isa} >= %{glib2_version}
Requires: glycin-libs%{?_isa} >= %{glycin_version}
Requires: shared-mime-info

# All modules previously provided by gdk-pixbuf itself are obsoleted by Glycin.
Obsoletes: %{name}-modules < %{version}-%{release}

# Most third-party pixbuf loaders are also obsolete. If Glycin supports the
# format, then it will take precedence and the third-party loader won't be used.
Obsoletes: avif-pixbuf-loader <= 1.1.1-4
Provides:  avif-pixbuf-loader
Obsoletes: heif-pixbuf-loader <= 1.20.1-2
Provides:  heif-pixbuf-loader
Obsoletes: jxl-pixbuf-loader <= 0.11.1-4
Provides:  jxl-pixbuf-loader
Obsoletes: rsvg-pixbuf-loader <= 2.61.0-1
Provides:  rsvg-pixbuf-loader
Obsoletes: webp-pixbuf-loader <= 0.2.7-4
Provides:  webp-pixbuf-loader

%description
gdk-pixbuf is an image loading library that can be extended by loadable
modules for new image formats. It is used by toolkits such as GTK+ or
clutter, and now uses Glycin for modern format support (JXL, HEIF, AVIF,
WebP, SVG).

%package devel
Summary: Development files for gdk-pixbuf2
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: glib2-devel%{?_isa} >= %{glib2_version}

%description devel
This package contains the libraries and header files that are needed
for writing applications that are using gdk-pixbuf2.

%package tests
Summary: Tests for the %{name} package
Requires: %{name}%{?_isa} = %{version}-%{release}

%description tests
The %{name}-tests package contains tests that can be used to verify
the functionality of the installed %{name} package.

%prep
%autosetup -n gdk-pixbuf-%{version} -p1

%build
meson setup \
    --prefix=%{_prefix} \
    --libdir=%{_libdir} \
    --buildtype=plain \
    --auto-features=disabled \
    -Ddocumentation=false \
    -Dman=false \
    -Dintrospection=enabled \
    -Dglycin=enabled \
    build
meson compile -C build

%install
DESTDIR=%{buildroot} meson install -C build

mkdir -p $RPM_BUILD_ROOT%{_libdir}/gdk-pixbuf-2.0/2.10.0/loaders
touch $RPM_BUILD_ROOT%{_libdir}/gdk-pixbuf-2.0/2.10.0/loaders.cache

# Rename gdk-pixbuf-query-loaders
(cd $RPM_BUILD_ROOT%{_bindir}
 mv gdk-pixbuf-query-loaders gdk-pixbuf-query-loaders-%{__isa_bits}
)
# ... and fix up gdk-pixbuf-query-loaders reference in the .pc file
sed -i -e 's/gdk-pixbuf-query-loaders/gdk-pixbuf-query-loaders-%{__isa_bits}/' \
    $RPM_BUILD_ROOT%{_libdir}/pkgconfig/gdk-pixbuf-2.0.pc

%find_lang gdk-pixbuf

%transfiletriggerin -- %{_libdir}/gdk-pixbuf-2.0/2.10.0/loaders
gdk-pixbuf-query-loaders-%{__isa_bits} --update-cache

%transfiletriggerpostun -- %{_libdir}/gdk-pixbuf-2.0/2.10.0/loaders
gdk-pixbuf-query-loaders-%{__isa_bits} --update-cache

%files -f gdk-pixbuf.lang
%license COPYING
%doc NEWS README.md
%{_libdir}/libgdk_pixbuf-2.0.so.0{,.*}
%{_libdir}/girepository-1.0
%dir %{_libdir}/gdk-pixbuf-2.0
%dir %{_libdir}/gdk-pixbuf-2.0/2.10.0
%dir %{_libdir}/gdk-pixbuf-2.0/2.10.0/loaders
%ghost %{_libdir}/gdk-pixbuf-2.0/2.10.0/loaders.cache
%{_bindir}/gdk-pixbuf-query-loaders-%{__isa_bits}

%files devel
%dir %{_includedir}/gdk-pixbuf-2.0
%{_includedir}/gdk-pixbuf-2.0/gdk-pixbuf
%{_libdir}/libgdk_pixbuf-2.0.so
%{_libdir}/pkgconfig/gdk-pixbuf-2.0.pc
%{_bindir}/gdk-pixbuf-csource
%{_bindir}/gdk-pixbuf-pixdata
%{_datadir}/gir-1.0/

%files tests
%{_libexecdir}/installed-tests
%{_datadir}/installed-tests

%changelog
* Sat Mar 21 2026 James Reilly <james@tunaos.org> - 2.44.5-1
- Build with glycin for JXL/HEIF/AVIF/WebP/SVG support
- Disable documentation build (no gi-docgen on EL10)
- Replace %%meson macros with explicit meson calls for EL10 compat
