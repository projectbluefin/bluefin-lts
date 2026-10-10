Name:           libcanberra
Version:        0.30
Release:        106%{?dist}
Summary:        Portable sound event library

License:        LGPL-2.1-or-later
URL:            http://0pointer.de/lennart/projects/libcanberra/
Source0:        https://0pointer.de/lennart/projects/libcanberra/libcanberra-%{version}.tar.xz

BuildRequires:  gcc
BuildRequires:  libtool
BuildRequires:  libtool-ltdl-devel
BuildRequires:  gettext-devel
BuildRequires:  pkgconfig(alsa)
BuildRequires:  pkgconfig(libpulse)
BuildRequires:  pkgconfig(vorbisfile)
BuildRequires:  pkgconfig(tdb)
BuildRequires:  pkgconfig(gtk+-3.0)

%description
libcanberra is a simple abstract interface for playing event sounds.
It implements the XDG Sound Theme and Name Specifications.

# Force replacement of system package
Obsoletes:      libcanberra < %{version}-%{release}
Conflicts:      libcanberra < %{version}-%{release}

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
Development files (headers, pkg-config file) for libcanberra.

%package        gtk3
Summary:        Gtk+ 3.x Bindings for libcanberra
Requires:       %{name}%{?_isa} = %{version}-%{release}
# Force replacement of system package
Obsoletes:      libcanberra-gtk3 < %{version}-%{release}
Conflicts:      libcanberra-gtk3 < %{version}-%{release}
Obsoletes:      libcanberra-gtk2 < %{version}-%{release}
Conflicts:      libcanberra-gtk2 < %{version}-%{release}

%description    gtk3
Gtk+ 3.x Bindings for libcanberra

%prep
%autosetup -p1

%build
%configure \
    --disable-static \
    --disable-gtk-doc \
    --enable-gtk3 \
    --disable-gtk \
    --with-builtin=dso

%make_build

%install
%make_install
find %{buildroot} -name '*.la' -delete

%ldconfig_scriptlets

%files
%license LGPL
%doc README
%{_libdir}/libcanberra.so.0{,.*}
# Plugins built with --with-builtin=dso
%{_libdir}/libcanberra-0.30/

%files devel
%{_includedir}/canberra.h
%{_includedir}/canberra-gtk.h
%{_libdir}/libcanberra.so
%{_libdir}/libcanberra-gtk3.so
%{_libdir}/pkgconfig/libcanberra.pc
%{_libdir}/pkgconfig/libcanberra-gtk3.pc
%{_datadir}/gtk-doc/html/libcanberra/
%{_datadir}/vala/vapi/libcanberra.vapi
%{_datadir}/vala/vapi/libcanberra-gtk.vapi

%files gtk3
%{_bindir}/canberra-gtk-play
%{_libdir}/libcanberra-gtk3.so.*
%{_libdir}/gtk-3.0/modules/libcanberra-gtk-module.so
%{_libdir}/gtk-3.0/modules/libcanberra-gtk3-module.so
%{_libdir}/gnome-settings-daemon-3.0/gtk-modules/canberra-gtk-module.desktop
%{_datadir}/gdm/autostart/LoginWindow/libcanberra-ready-sound.desktop
%{_datadir}/gnome/autostart/libcanberra-login-sound.desktop
%{_datadir}/gnome/shutdown/libcanberra-logout-sound.sh

%changelog
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 0.30-106
- Revert fake tecla hack, using real tecla package
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 0.30-105
- Bump fake tecla version to 100.0
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 0.30-104
- Fix missing files in libcanberra-gtk3 and devel subpackages
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 0.30-103
- Re-enable REAL libcanberra-gtk3 now that we have confirmed GTK3 is in EL10
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 0.30-101
- Obsolete libcanberra-gtk2 as well
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 0.30-100
- Option C: Virtual provides for libcanberra-gtk3 to satisfy system deps
- Fake libcanberra-gtk3.so.0 with a symlink to base libcanberra
- Bump release to 100 to override system package
