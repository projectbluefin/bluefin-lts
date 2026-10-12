Name:           gi-docgen
Version:        2026.1
Release:        100%{?dist}
Summary:        A documentation generator for GObject-based libraries
License:        Apache-2.0 OR GPL-3.0-or-later
URL:            https://gnome.pages.gitlab.gnome.org/gi-docgen/
Source0:        https://files.pythonhosted.org/packages/source/g/gi-docgen/gi_docgen-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pip
BuildRequires:  python3-wheel
BuildRequires:  python3-jinja2
BuildRequires:  python3-markdown
BuildRequires:  python3-markupsafe
BuildRequires:  python3-pygments
BuildRequires:  python3dist(typogrify)

Requires:       python3-jinja2
Requires:       python3-markdown
Requires:       python3-markupsafe
Requires:       python3-pygments
Requires:       python3dist(typogrify)

%description
gi-docgen is a document generator for GObject-based libraries. GObject-based
libraries use GObject Introspection to provide a common interface for
multiple languages. gi-docgen uses the GObject Introspection data to
generate documentation for these libraries.

%prep
%autosetup -n gi_docgen-%{version}

%build
python3 setup.py bdist_wheel

%install
pip3 install --root=%{buildroot} --no-deps dist/*.whl

%files
%{python3_sitelib}/gidocgen/
%{python3_sitelib}/gi_docgen-%{version}.dist-info/
%doc README.md
%{_bindir}/gi-docgen
%{_datadir}/pkgconfig/gi-docgen.pc
%{_mandir}/man1/gi-docgen.1*

%changelog
* Thu Mar 12 2026 Conductor <james@conductor.local> - 2025.5-1
- Initial bootstrap build for EL10
