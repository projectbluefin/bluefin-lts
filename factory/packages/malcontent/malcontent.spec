Name:           malcontent
Version:        0.14.0
Release:        3%{?dist}
Summary:        Parental controls implementation

License:        LGPL-2.1-only AND CC-BY-3.0
URL:            https://gitlab.freedesktop.org/pwithnall/%{name}/
Source0:        https://tecnocode.co.uk/downloads/%{name}/%{name}-%{version}.tar.xz
Source1:        https://gitlab.gnome.org/pwithnall/libgsystemservice/-/archive/0.3.0/libgsystemservice-0.3.0.tar.bz2
Source2:        gvdb.tar.xz
Source3:        tinycdb-0.81.tar.gz

BuildRequires:  gettext
BuildRequires:  gi-docgen
BuildRequires:  meson
BuildRequires:  cmake
BuildRequires:  git
BuildRequires:  gcc
BuildRequires:  itstool
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib
BuildRequires:  pkgconfig(gobject-introspection-1.0)
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(polkit-gobject-1)
BuildRequires:  pkgconfig(accountsservice)
BuildRequires:  pkgconfig(gtk4)
BuildRequires:  pkgconfig(libadwaita-1)
BuildRequires:  pkgconfig(appstream)
BuildRequires:  pkgconfig(flatpak)
BuildRequires:  pkgconfig(glib-testing-0)
BuildRequires:  pkgconfig(gnome-desktop-4)
BuildRequires:  pam-devel
BuildRequires:  libsoup3-devel

Provides:       bundled(gvdb)
Provides:       bundled(libgsystemservice)
Provides:       bundled(tinycdb)

Requires: polkit

%description
libmalcontent implements parental controls support which can be used by
applications to filter or limit the access of child accounts to inappropriate
content.

%package control
Summary:        Parental Controls UI
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description control
This package contains a user interface for querying and setting parental
controls for users.

%package pam
Summary:        Parental Controls PAM Module

%description pam
This package contains a PAM module which prevents logins for users who have
exceeded their allowed computer time.

%package tools
Summary:        Parental Controls Tools
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description tools
This package contains tools for querying and updating the parental controls
settings for users.

%package ui-devel
Summary:        Development files for libmalcontent-ui
Requires:       %{name}-ui-libs%{?_isa} = %{version}-%{release}

%description ui-devel
Development headers for libmalcontent-ui.

%package ui-libs
Summary:        Libraries for %{name}

%description ui-libs
This package contains libmalcontent-ui.

%package devel
Summary:        Development files for %{name}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description devel
Development headers for libmalcontent.

%package libs
Summary:        Libraries for %{name}

%description libs
This package contains libmalcontent.

%package doc
Summary:        Documentation for %{name}

%description doc
Documentation for libmalcontent.

%prep
%autosetup -p1 -n %{name}-%{version} -S git
tar -xf %{SOURCE1} -C subprojects
mv subprojects/libgsystemservice-0.3.0 subprojects/libgsystemservice
tar -xf %{SOURCE2} -C subprojects
tar -xf %{SOURCE3} -C subprojects
cp subprojects/packagefiles/tinycdb/meson.build subprojects/tinycdb-0.81

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
    --sysconfdir=%{_sysconfdir} \
    --localstatedir=%{_localstatedir} \
    --wrap-mode=nodownload \
    -Dui=enabled \
    -Dinstalled_tests=false
ninja -C _build -j%{_smp_build_ncpus}

%install
DESTDIR=%{buildroot} ninja -C _build install
%find_lang %{name} --with-gnome

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/org.freedesktop.MalcontentControl.desktop
appstream-util validate-relax --nonet %{buildroot}%{_datadir}/metainfo/org.freedesktop.MalcontentControl.metainfo.xml

%files -f %{name}.lang
%license COPYING COPYING-DOCS
%doc README.md
%{_datadir}/accountsservice/interfaces/
%{_datadir}/dbus-1/interfaces/
%{_datadir}/polkit-1/actions/*.policy
%{_datadir}/polkit-1/rules.d/com.endlessm.ParentalControls.rules
%{_libexecdir}/malcontent-timer-extension-agent
%{_libexecdir}/malcontent-timerd
%{_libexecdir}/malcontent-webd
%{_libexecdir}/malcontent-webd-update
%{_datadir}/dbus-1/services/org.freedesktop.MalcontentControl.service
%{_datadir}/dbus-1/system-services/org.freedesktop.MalcontentTimer1.ExtensionAgent.service
%{_datadir}/dbus-1/system-services/org.freedesktop.MalcontentTimer1.service
%{_datadir}/dbus-1/system-services/org.freedesktop.MalcontentWeb1.service
%{_datadir}/dbus-1/system.d/org.freedesktop.MalcontentTimer1.ExtensionAgent.conf
%{_datadir}/dbus-1/system.d/org.freedesktop.MalcontentTimer1.conf
%{_datadir}/dbus-1/system.d/org.freedesktop.MalcontentWeb1.conf
%{_mandir}/man8/malcontent-timer-extension-agent.8*
%{_mandir}/man8/malcontent-timerd.8*
%{_mandir}/man8/malcontent-webd.8*
%{_unitdir}/malcontent-timer-extension-agent.service
%{_unitdir}/malcontent-timerd.service
%{_unitdir}/malcontent-webd-update.service
%{_unitdir}/malcontent-webd-update.timer
%{_unitdir}/malcontent-webd.service
%{_sysusersdir}/malcontent-timer-extension-agent.conf
%{_sysusersdir}/malcontent-timerd.conf
%{_sysusersdir}/malcontent-webd.conf
%exclude %{_libexecdir}/installed-tests/malcontent-webd-update-1/malcontent-webd-template.py

%files control
%license COPYING
%doc README.md
%{_bindir}/malcontent-control
%{_datadir}/applications/org.freedesktop.MalcontentControl.desktop
%{_datadir}/icons/hicolor/scalable/apps/org.freedesktop.MalcontentControl.svg
%{_datadir}/icons/hicolor/symbolic/apps/org.freedesktop.MalcontentControl-symbolic.svg
%{_datadir}/metainfo/org.freedesktop.MalcontentControl.metainfo.xml

%files pam
%license COPYING
%{_libdir}/security/pam_malcontent.so

%files tools
%license COPYING
%{_bindir}/malcontent-client
%{_mandir}/man8/malcontent-client.8.*

%files ui-devel
%license COPYING
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/MalcontentUi-1.gir
%{_libdir}/libmalcontent-ui-1.so
%{_includedir}/malcontent-ui-1/
%{_libdir}/pkgconfig/malcontent-ui-1.pc

%files ui-libs
%license COPYING
%doc README.md
%dir %{_libdir}/girepository-1.0/
%{_libdir}/girepository-1.0/MalcontentUi-1.typelib
%{_libdir}/libmalcontent-ui-1.so.*

%files devel
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Malcontent-0.gir
%{_includedir}/malcontent-0/
%{_libdir}/libmalcontent-0.so
%{_libdir}/pkgconfig/malcontent-0.pc

%files libs
%license COPYING
%doc README.md
%dir %{_libdir}/girepository-1.0/
%{_libdir}/girepository-1.0/Malcontent-0.typelib
%{_libdir}/libmalcontent-0.so.*
%{_libdir}/libnss_malcontent.so*

%files doc
%{_docdir}/libmalcontent-0
%{_docdir}/libmalcontent-ui-1

%changelog
* Mon Mar 30 2026 James Reilly <jreilly1821@gmail.com> - 0.14.0-3
- Commit tinycdb-0.81.tar.gz locally; COPR SRPM builder rejects HTTP URLs
- Change Source3 from HTTP URL to local filename

* Mon Mar 30 2026 James Reilly <jreilly1821@gmail.com> - 0.14.0-2
- Remove spurious gtk-doc BR (malcontent uses gi-docgen, not gtk-doc)

* Mon Mar 30 2026 James Reilly <jreilly1821@gmail.com> - 0.14.0-1
- Initial package for EL10; enables parental controls in gnome-initial-setup
- Explicit meson/ninja invocations (no %%meson macros, COPR non-interactive bash)
- gvdb bundled source fetched from Fedora lookaside
