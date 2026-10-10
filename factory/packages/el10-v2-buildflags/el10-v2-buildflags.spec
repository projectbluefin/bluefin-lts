Name:           el10-v2-buildflags
Version:        4
Release:        1%{?dist}
Summary:        Override RPM optflags for x86_64_v2 buildroots on EL10
License:        MIT
BuildArch:      noarch

%description
Overrides %%__cflags_arch_x86_64_level to force -march=x86-64-v2 on EL10.
EL10's redhat-rpm-config evaluates this macro as -v3 for all RHEL > 9,
but some COPR build hosts only support x86_64_v2 and cannot execute v3 code.

%install
mkdir -p %{buildroot}%{_sysconfdir}/rpm
printf '%%%%__cflags_arch_x86_64_level -v2\n' \
    > %{buildroot}%{_sysconfdir}/rpm/macros.el10-v2-buildflags

%files
%{_sysconfdir}/rpm/macros.el10-v2-buildflags
