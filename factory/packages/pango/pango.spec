%global glib2_version 2.80
%global fribidi_version 1.0.6
%global libthai_version 0.1.9
%global harfbuzz_version 8.4.0
%global fontconfig_version 2.17.0
%global libXft_version 2.0.0
%global cairo_version 1.18
%global freetype_version 2.1.5

Name:    pango
Version: 1.57.0
Release: %autorelease
Summary: System for layout and rendering of internationalized text

License: LGPL-2.0-or-later
URL:     https://pango.gnome.org/
Source0: https://download.gnome.org/sources/%{name}/1.57/%{name}-%{version}.tar.xz

BuildRequires: pkgconfig(cairo) >= %{cairo_version}
BuildRequires: pkgconfig(cairo-gobject) >= %{cairo_version}
BuildRequires: pkgconfig(freetype2) >= %{freetype_version}
BuildRequires: pkgconfig(glib-2.0) >= %{glib2_version}
BuildRequires: pkgconfig(fontconfig) >= %{fontconfig_version}
BuildRequires: pkgconfig(harfbuzz) >= %{harfbuzz_version}
BuildRequires: pkgconfig(libthai) >= %{libthai_version}
BuildRequires: pkgconfig(xft) >= %{libXft_version}
BuildRequires: pkgconfig(fribidi) >= %{fribidi_version}
BuildRequires: pkgconfig(gobject-introspection-1.0)
BuildRequires: help2man
BuildRequires: meson
BuildRequires: gcc gcc-c++
BuildRequires: gi-docgen
BuildRequires: python3-docutils

Requires: glib2%{?_isa} >= %{glib2_version}
Requires: freetype%{?_isa} >= %{freetype_version}
Requires: fontconfig%{?_isa} >= %{fontconfig_version}
Requires: cairo%{?_isa} >= %{cairo_version}
Requires: harfbuzz%{?_isa} >= %{harfbuzz_version}
Requires: libthai%{?_isa} >= %{libthai_version}
Requires: libXft%{?_isa} >= %{libXft_version}
Requires: fribidi%{?_isa} >= %{fribidi_version}

Provides: pango-tests = %{version}-%{release}
Obsoletes: pango-tests < 1.54.0-1

%description
Pango is a library for laying out and rendering of text, with an emphasis
on internationalization. Pango can be used anywhere that text layout is needed,
though most of the work on Pango so far has been done in the context of the
GTK+ widget toolkit. Pango forms the core of text and font handling for GTK+.

Pango is designed to be modular; the core Pango layout engine can be used
with different font backends.

The integration of Pango with Cairo provides a complete solution with high
quality text handling and graphics rendering.

%package devel
Summary: Development files for pango
Requires: pango%{?_isa} = %{version}-%{release}
Requires: glib2-devel%{?_isa} >= %{glib2_version}
Requires: freetype-devel%{?_isa} >= %{freetype_version}
Requires: fontconfig-devel%{?_isa} >= %{fontconfig_version}
Requires: cairo-devel%{?_isa} >= %{cairo_version}

%description devel
The pango-devel package includes the header files for the pango package.

%package doc
Summary: Developer documentation for pango
Requires: pango%{?_isa} = %{version}-%{release}
# Because web fonts from upstream are not bundled in the gi-docgen package,
# packages containing documentation generated with gi-docgen should depend on
# this metapackage to ensure the proper system fonts are present.
Recommends: gi-docgen-fonts

%description doc
The pango-doc package contains developer documentation for the pango package.


%prep
rm -rf subprojects/fontconfig/
rm -f subprojects/fontconfig.wrap
%autosetup -n pango-%{version} -p1


%build
export CFLAGS='-std=c11 %optflags'
meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain -Dfontconfig=enabled build \
  -Dbuild-testsuite=true \
  -Dbuild-examples=true \
  -Ddocumentation=true

meson compile -C build


%install
rm -rf %{buildroot}/etc/fonts %{buildroot}/usr/bin/fc-* %{buildroot}/usr/lib64/libfontconfig* %{buildroot}/usr/lib64/pkgconfig/fontconfig.pc %{buildroot}/usr/include/fontconfig %{buildroot}/usr/share/fontconfig %{buildroot}/usr/share/gettext/its/fontconfig* %{buildroot}/usr/share/xml/fontconfig %{buildroot}/var/cache/fontconfig %{buildroot}/usr/share/locale/*/LC_MESSAGES/fontconfig*
DESTDIR=%{buildroot} meson install -C build

PANGOXFT_SO=$RPM_BUILD_ROOT%{_libdir}/libpangoxft-1.0.so
if ! test -e $PANGOXFT_SO; then
        echo "$PANGOXFT_SO not found; did not build with Xft support?"
        ls $RPM_BUILD_ROOT%{_libdir}
        exit 1
fi













%files
%license COPYING
%doc NEWS README.md
%{_bindir}/*
%{_libdir}/*.so.*
%{_libdir}/girepository-1.0/*

%files devel
%{_includedir}/*
%{_libdir}/*.so
%{_libdir}/pkgconfig/*.pc
%{_datadir}/gir-1.0/*

%files doc
%{_datadir}/doc/*

%changelog
%autochangelog
