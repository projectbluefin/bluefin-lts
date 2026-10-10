Name:           sqlcipher
Version:        4.5.2
Release:        8%{?dist}
Summary:        Fork of the SQLite database library that adds 256 bit AES encryption

License:        BSD-3-Clause
URL:            https://github.com/sqlcipher/sqlcipher
Source:         %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildRequires:  make
BuildRequires:  gcc
BuildRequires:  pkgconfig(libcrypto)
BuildRequires:  pkgconfig(sqlite3)
BuildRequires:  readline-devel
BuildRequires:  tcl

%description
SQLCipher is an open source library that provides transparent, secure 256-bit
AES encryption of SQLite database files. SQLCipher has been adopted as a secure
database solution by many commercial and open source products, making it one of
the most popular encrypted database platforms for Mobile, Embedded, and Desktop
applications


%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}
%description devel
The %{name}-devel package contains libraries for
developing applications that use %{name}.


%prep
%setup -q


%build
# recommended in README.md ## Compiling section
CFLAGS="%{optflags} -DSQLITE_HAS_CODEC -DSQLITE_TEMP_STORE=2"
LDFLAGS="%{?__global_ldflags} -lcrypto"
%configure \
    --enable-tempstore=yes \
    --enable-releasemode \
    --disable-static \
    --disable-tcl

# fix/workaround hard-coded rpaths
sed -i 's|^hardcode_libdir_flag_spec=.*|hardcode_libdir_flag_spec=""|g' libtool
sed -i 's|^runpath_var=LD_RUN_PATH|runpath_var=DIE_RPATH_DIE|g' libtool

%make_build


%install
%make_install

rm -fv %{buildroot}%{_libdir}/lib*.la


%files
%doc README.md
%license LICENSE
%{_bindir}/sqlcipher
%{_libdir}/libsqlcipher-3.39.2.so.0*

%files devel
%{_includedir}/sqlcipher
%{_libdir}/libsqlcipher.so
%{_libdir}/pkgconfig/sqlcipher.pc


%changelog
* Sat Jan 17 2026 Fedora Release Engineering <releng@fedoraproject.org> - 4.5.2-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_44_Mass_Rebuild

* Fri Jul 25 2025 Fedora Release Engineering <releng@fedoraproject.org> - 4.5.2-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_43_Mass_Rebuild

* Sun Jan 19 2025 Fedora Release Engineering <releng@fedoraproject.org> - 4.5.2-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_42_Mass_Rebuild

* Sat Jul 20 2024 Fedora Release Engineering <releng@fedoraproject.org> - 4.5.2-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_41_Mass_Rebuild

* Sat Jan 27 2024 Fedora Release Engineering <releng@fedoraproject.org> - 4.5.2-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_40_Mass_Rebuild

* Sat Jul 22 2023 Fedora Release Engineering <releng@fedoraproject.org> - 4.5.2-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_39_Mass_Rebuild

* Sat Jan 21 2023 Fedora Release Engineering <releng@fedoraproject.org> - 4.5.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_38_Mass_Rebuild

* Wed Aug 24 2022 Carl George <carl@george.computer> - 4.5.2-1
- Latest upstream, resolves rhbz#2018427

* Sat Jul 23 2022 Fedora Release Engineering <releng@fedoraproject.org> - 4.4.3-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_37_Mass_Rebuild

* Sat Jan 22 2022 Fedora Release Engineering <releng@fedoraproject.org> - 4.4.3-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_36_Mass_Rebuild

* Tue Sep 14 2021 Sahana Prasad <sahana@redhat.com> - 4.4.3-3
- Rebuilt with OpenSSL 3.0.0

* Fri Jul 23 2021 Fedora Release Engineering <releng@fedoraproject.org> - 4.4.3-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_35_Mass_Rebuild

* Fri Mar 19 2021 Tadej Janež <tadej.j@nez.si> - 4.4.3-1
- Update to 4.4.3 (RHBZ#1528491)

* Wed Jan 27 2021 Fedora Release Engineering <releng@fedoraproject.org> - 3.4.1-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Wed Jul 29 2020 Fedora Release Engineering <releng@fedoraproject.org> - 3.4.1-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_33_Mass_Rebuild

* Fri Jan 31 2020 Fedora Release Engineering <releng@fedoraproject.org> - 3.4.1-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_32_Mass_Rebuild

* Sat Jul 27 2019 Fedora Release Engineering <releng@fedoraproject.org> - 3.4.1-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_31_Mass_Rebuild

* Sun Feb 17 2019 Igor Gnatenko <ignatenkobrain@fedoraproject.org> - 3.4.1-5
- Rebuild for readline 8.0

* Sun Feb 03 2019 Fedora Release Engineering <releng@fedoraproject.org> - 3.4.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_30_Mass_Rebuild

* Sat Jul 14 2018 Fedora Release Engineering <releng@fedoraproject.org> - 3.4.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_29_Mass_Rebuild

* Fri Feb 09 2018 Fedora Release Engineering <releng@fedoraproject.org> - 3.4.1-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_28_Mass_Rebuild

* Wed Aug 02 2017 Rex Dieter <rdieter@fedoraproject.org> - 3.4.1-1
- 3.4.1

* Thu Jul 27 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.3.1-7
- Rebuilt for https://fedoraproject.org/wiki/Fedora_27_Mass_Rebuild

* Sat Feb 11 2017 Fedora Release Engineering <releng@fedoraproject.org> - 3.3.1-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_26_Mass_Rebuild

* Thu Jan 12 2017 Igor Gnatenko <ignatenko@redhat.com> - 3.3.1-5
- Rebuild for readline 7.x

* Wed Jul 27 2016 siddharth.kde@gmail.com - 3.3.1-4
- remove tcl and add openssl-devel as build requires

* Tue Jul 26 2016 Rex Dieter <rdieter@fedoraproject.org> - 3.3.1-3
- rebuilt fixing review requests in bz#1310294

* Wed Mar 09 2016 gripen <siddharth.kde@gmail.com> - 3.3.1-2
- rebuilt fixing review requests in bz#1310294

* Sat Feb 20 2016 Siddharth Sharma <siddharth.kde@gmail.com> - 3.3.1-1
- Init sqlcipher package


