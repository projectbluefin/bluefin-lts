%global tarball_version %%(echo %{version} | tr '~' '.')

Name:           tecla
Version:        50~rc
Release:        100%{?dist}
Summary:        Keyboard layout viewer

License:        GPL-2.0-or-later
URL:            https://gitlab.gnome.org/GNOME/tecla
Source:         https://download.gnome.org/sources/tecla/50/tecla-%{tarball_version}.tar.xz

BuildRequires:  gcc
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(gtk4-wayland)
BuildRequires:  pkgconfig(libadwaita-1)
BuildRequires:  pkgconfig(wayland-client)
BuildRequires:  pkgconfig(xkbcommon)
BuildRequires:  /usr/bin/desktop-file-validate

%description
Tecla is a keyboard layout viewer. It uses GTK/Libadwaita for UI, and
libxkbcommon to deal with keyboard maps.


%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains a pkg-config file for
developing applications that use %{name}.


%prep
%autosetup -p1 -n tecla-%{tarball_version}


%build
%meson
%meson_build


%install
%meson_install

%find_lang tecla


%check
desktop-file-validate %{buildroot}%{_datadir}/applications/org.gnome.Tecla.desktop
%meson_test


%files -f tecla.lang
%license LICENSE
%doc NEWS README.md
%{_bindir}/tecla
%{_datadir}/applications/org.gnome.Tecla.desktop
%{_datadir}/icons/hicolor/scalable/apps/org.gnome.Tecla.svg
%{_datadir}/icons/hicolor/symbolic/apps/org.gnome.Tecla-symbolic.svg


%files devel
%{_datadir}/pkgconfig/tecla.pc


%changelog
* Sat Mar 14 2026 James Reilly <jreilly1821@gmail.com> - 50~rc-100
- Initial build for GNOME 50 bootstrap on EL10
