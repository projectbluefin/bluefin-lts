Name:           gobject-introspection
Version:        1.86.0
Release:        2%{?dist}
Summary:        Introspection system for GObject-based libraries
License:        GPL-2.0-or-later AND LGPL-2.0-or-later AND MIT
URL:            https://wiki.gnome.org/Projects/GObjectIntrospection
Source0:        https://download.gnome.org/sources/%{name}/1.86/%{name}-%{version}.tar.xz

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  flex
BuildRequires:  bison
BuildRequires:  pkgconfig(glib-2.0) >= 2.80.0
BuildRequires:  pkgconfig(cairo)
BuildRequires:  pkgconfig(cairo-gobject)
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-mako
BuildRequires:  python3-markdown
BuildRequires:  gtk-doc

Requires:       python3-mako
Requires:       python3-markdown
Requires:       python3-setuptools

%description
GObject Introspection is a project that aims to describe the APIs of
GObject-based libraries.

%package devel
Summary:        Libraries and headers for gobject-introspection
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       libtool
Requires:       python3-mako
Requires:       python3-markdown
Requires:       python3-setuptools

%description devel
Libraries and headers for gobject-introspection.

%prep
%autosetup -n gobject-introspection-%{version}
# Remove glib version constraints from meson.build
python3 -c "
import re
content = open('meson.build').read()
content = re.sub(r\"dependency\((['\\\"][\w.-]+['\\\"]),\s*version:\s*[^,)]+,?\", r\"dependency(\1,\", content)
content = content.replace(\",)\", \")\")
with open('meson.build', 'w') as f: f.write(content)
"

%build
meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain build \
    -Dgtk_doc=true
meson compile -C build

%install
DESTDIR=%{buildroot} meson install -C build

%files
%{_libdir}/libgirepository-1.0.so.1*
%{_libdir}/girepository-1.0/
%{_libdir}/gobject-introspection/
%{_bindir}/g-ir-compiler
%{_bindir}/g-ir-generate
%{_bindir}/g-ir-inspect
%{_bindir}/g-ir-scanner
%{_bindir}/g-ir-annotation-tool
%{_bindir}/g-ir-doc-tool
%{_datadir}/gir-1.0/
%{_datadir}/gobject-introspection-1.0/
%{_mandir}/man1/g-ir-*

%files devel
%{_includedir}/gobject-introspection-1.0/
%{_libdir}/libgirepository-1.0.so
%{_libdir}/pkgconfig/gobject-introspection-1.0.pc
%{_libdir}/pkgconfig/gobject-introspection-no-export-1.0.pc
%{_datadir}/aclocal/introspection.m4
%{_datadir}/gtk-doc/html/gi/

%changelog
* Mon Apr 07 2026 James Reilly <jreilly1821@gmail.com> - 1.86.0-2
- Add Requires: libtool, python3-mako/markdown/setuptools to devel subpackage
  so downstream packages (vala, libgee) get gcc pulled in transitively.

* Thu Mar 12 2026 Conductor <james@conductor.local> - 1.86.0-1
- Bootstrap build
