#!/usr/bin/env bats

# Unit tests for build_scripts/26-packages-post.sh
# Run with: bats tests/unit/packages_post_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
POST_SCRIPT="${SCRIPT_DIR}/../../build_scripts/26-packages-post.sh"

# Rewrite every absolute path the script writes to into the sandbox, then run
# it. Line 1 is skipped so the shebang keeps pointing at the real /usr/bin/env.
patch_and_run() {
    PATCHED_SCRIPT="${TEST_ROOT}/26-packages-post-patched.sh"
    sed \
        -e "1!s|/usr/|${TEST_ROOT}/usr/|g" \
        -e "1!s|/etc/|${TEST_ROOT}/etc/|g" \
        -e "1!s|/lib/modules/|${TEST_ROOT}/lib/modules/|g" \
        -e "1!s|/tmp/bluefin.pdf|${TEST_ROOT}/tmp/bluefin.pdf|g" \
        "${POST_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    run bash "${PATCHED_SCRIPT}"
}

# Line number of the first command invocation in CMD_LOG matching a pattern.
cmd_line() {
    grep -n -- "$1" "${CMD_LOG}" | head -1 | cut -d: -f1
}

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    CMD_LOG="${TEST_ROOT}/cmd.log"

    SCHEMA_DIR="${TEST_ROOT}/usr/share/glib-2.0/schemas"
    FASTFETCH="${TEST_ROOT}/usr/share/ublue-os/fastfetch.jsonc"
    ZRAM_CONF="${TEST_ROOT}/usr/lib/systemd/zram-generator.conf"
    FIREWALLD_ZONE="${TEST_ROOT}/usr/lib/firewalld/zones/FedoraWorkstation.xml"
    FIREWALLD_CONF="${TEST_ROOT}/etc/firewalld/firewalld.conf"
    FLATHUB_REPO="${TEST_ROOT}/etc/flatpak/remotes.d/flathub.flatpakrepo"
    RESUME_CONF="${TEST_ROOT}/etc/dracut.conf.d/resume.conf"
    SUDOERS="${TEST_ROOT}/etc/sudoers"
    MODULES_DIR="${TEST_ROOT}/lib/modules"

    mkdir -p "${STUB_BIN}" "${SCHEMA_DIR}" "${TEST_ROOT}/tmp" \
        "$(dirname "${FASTFETCH}")" "$(dirname "${ZRAM_CONF}")" \
        "$(dirname "${FIREWALLD_ZONE}")" "$(dirname "${FIREWALLD_CONF}")" \
        "$(dirname "${RESUME_CONF}")" "${TEST_ROOT}/usr/bin" "${MODULES_DIR}"

    # /usr/bin/dracut is called by absolute path, so the stub has to live there.
    DRACUT="${TEST_ROOT}/usr/bin/dracut"

    # Kernel packages the rpm stub reports. The script keeps the LAST match.
    export STUB_RPM_QA="kernel-6.12.0-55.el10.x86_64
kernel-core-6.12.0-55.el10.x86_64
kernel-6.12.9-100.el10.x86_64"

    # When 1, curl writes the payload the following grep assertions expect.
    export STUB_CURL_WRITES=1
    export STUB_CURL_EXIT=0
    export STUB_GHCURL_EXIT=0

    printf '{\n  "logo": "\xf3\xb0\xa3\x9b CentOS"\n}\n' > "${FASTFETCH}"
    printf "picture-uri='file:///usr/share/backgrounds/bluefin/12.jpg'\n" \
        > "${SCHEMA_DIR}/zz0-bluefin-modifications.gschema.override"
    printf 'Defaults secure_path = /usr/local/sbin:/usr/sbin:/usr/bin\n' > "${SUDOERS}"
    printf '[config]\nDefaultZone=public\nIPv6_rpfilter=yes\n' > "${FIREWALLD_CONF}"

    # The script picks the newest kernel dir with `ls -1 ... | tail -1`.
    mkdir -p "${MODULES_DIR}/6.12.0-55.el10.x86_64" "${MODULES_DIR}/6.12.9-100.el10.x86_64"

    # chsh/lchsh must exist for the footgun removal to be observable.
    : > "${TEST_ROOT}/usr/bin/chsh"
    : > "${TEST_ROOT}/usr/bin/lchsh"

    cat > "${STUB_BIN}/curl" <<EOF
#!/usr/bin/env bash
echo "curl \$*" >> "${CMD_LOG}"
out=""
url=""
prev=""
for arg in "\$@"; do
    [[ "\$prev" == "-o" ]] && out="\$arg"
    case "\$arg" in
        http*) url="\$arg" ;;
    esac
    prev="\$arg"
done
if [[ "\${STUB_CURL_EXIT}" != "0" ]]; then
    exit "\${STUB_CURL_EXIT}"
fi
if [[ -n "\$out" && "\${STUB_CURL_WRITES}" == "1" ]]; then
    mkdir -p "\$(dirname "\$out")"
    case "\$url" in
        *zram-generator.conf) printf '[zram0]\nzram-size = min(ram / 2, 8192)\n' > "\$out" ;;
        *FedoraWorkstation.xml) printf '<zone>\n  <port protocol="udp" port="1025-65535"/>\n</zone>\n' > "\$out" ;;
        *) printf 'stub payload\n' > "\$out" ;;
    esac
elif [[ -n "\$out" ]]; then
    mkdir -p "\$(dirname "\$out")"
    : > "\$out"
fi
exit 0
EOF

    cat > "${STUB_BIN}/ghcurl" <<EOF
#!/usr/bin/env bash
echo "ghcurl \$*" >> "${CMD_LOG}"
if [[ "\${STUB_GHCURL_EXIT}" != "0" ]]; then
    exit "\${STUB_GHCURL_EXIT}"
fi
out=""
prev=""
for arg in "\$@"; do
    [[ "\$prev" == "-Lo" ]] && out="\$arg"
    prev="\$arg"
done
if [[ -n "\$out" ]]; then
    mkdir -p "\$(dirname "\$out")"
    printf 'PDF\n' > "\$out"
fi
exit 0
EOF

    cat > "${STUB_BIN}/rpm" <<EOF
#!/usr/bin/env bash
echo "rpm \$*" >> "${CMD_LOG}"
printf '%s\n' "\${STUB_RPM_QA}"
exit 0
EOF

    for stub in glib-compile-schemas gdk-pixbuf-query-loaders-64 depmod; do
        cat > "${STUB_BIN}/${stub}" <<EOF
#!/usr/bin/env bash
echo "${stub} \$*" >> "${CMD_LOG}"
exit 0
EOF
    done

    cat > "${DRACUT}" <<EOF
#!/usr/bin/env bash
echo "dracut \$*" >> "${CMD_LOG}"
exit 0
EOF

    chmod +x "${STUB_BIN}"/* "${DRACUT}"
    export PATH="${STUB_BIN}:${PATH}"
    export TEST_ROOT STUB_BIN CMD_LOG SCHEMA_DIR FASTFETCH ZRAM_CONF \
        FIREWALLD_ZONE FIREWALLD_CONF FLATHUB_REPO RESUME_CONF SUDOERS \
        MODULES_DIR DRACUT
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Script smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: exits 0 on the happy path" {
    patch_and_run
    [ "$status" -eq 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Branding: fastfetch + wallpaper schema
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: strips the CentOS glyph from fastfetch.jsonc" {
    patch_and_run
    [ "$status" -eq 0 ]
    run grep -c $'\uf08db' "${FASTFETCH}"
    [ "$status" -ne 0 ]
    grep -q "CentOS" "${FASTFETCH}"
}

@test "packages-post: rewrites the hardcoded wallpaper month to the current month" {
    patch_and_run
    [ "$status" -eq 0 ]
    override="${SCHEMA_DIR}/zz0-bluefin-modifications.gschema.override"
    grep -q "/$(date +%m).jpg" "${override}"
    # December is the hardcoded value; it must be gone unless it IS December.
    if [ "$(date +%m)" != "12" ]; then
        run grep -q "/12.jpg" "${override}"
        [ "$status" -ne 0 ]
    fi
}

@test "packages-post: recompiles the glib schemas after editing the override" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "glib-compile-schemas ${SCHEMA_DIR}" "${CMD_LOG}"
}

@test "packages-post: refreshes the gdk-pixbuf loader cache" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "gdk-pixbuf-query-loaders-64 --update-cache" "${CMD_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Offline documentation
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: installs the offline documentation PDF" {
    patch_and_run
    [ "$status" -eq 0 ]
    [ -f "${TEST_ROOT}/usr/share/doc/bluefin/bluefin.pdf" ]
}

@test "packages-post: fetches the PDF with ghcurl, not bare curl" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "ghcurl https://github.com/projectbluefin/documentation/" "${CMD_LOG}"
}

@test "packages-post: propagates a ghcurl failure instead of shipping a partial image" {
    export STUB_GHCURL_EXIT=22
    patch_and_run
    [ "$status" -eq 22 ]
    [ ! -f "${TEST_ROOT}/usr/share/doc/bluefin/bluefin.pdf" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Flathub remote
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: writes the Flathub remote into /etc/flatpak/remotes.d" {
    patch_and_run
    [ "$status" -eq 0 ]
    [ -f "${FLATHUB_REPO}" ]
    grep -q "dl.flathub.org/repo/flathub.flatpakrepo" "${CMD_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# zram + firewalld: downloads are content-verified, not just fetched
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: downloads zram-generator.conf to the systemd path" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "zram-size =" "${ZRAM_CONF}"
}

@test "packages-post: fails when the zram config lacks zram-size" {
    export STUB_CURL_WRITES=0
    patch_and_run
    [ "$status" -ne 0 ]
}

@test "packages-post: retries transient curl failures rather than one-shotting" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "--retry" "${CMD_LOG}"
    grep -q -- "--fail" "${CMD_LOG}"
}

@test "packages-post: propagates a hard curl failure" {
    export STUB_CURL_EXIT=6
    patch_and_run
    [ "$status" -eq 6 ]
}

@test "packages-post: downloads the FedoraWorkstation zone and verifies the udp port range" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q 'port="1025-65535"' "${FIREWALLD_ZONE}"
}

@test "packages-post: switches firewalld to the FedoraWorkstation zone" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "^DefaultZone=FedoraWorkstation$" "${FIREWALLD_CONF}"
}

@test "packages-post: loosens IPv6 reverse path filtering" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "^IPv6_rpfilter=loose$" "${FIREWALLD_CONF}"
}

@test "packages-post: fails when firewalld.conf has no DefaultZone line to rewrite" {
    printf '[config]\nIPv6_rpfilter=yes\n' > "${FIREWALLD_CONF}"
    patch_and_run
    [ "$status" -ne 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# initramfs: depmod + dracut kernel resolution
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: runs depmod against the newest /lib/modules entry" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "depmod -a 6.12.9-100.el10.x86_64" "${CMD_LOG}"
}

@test "packages-post: enables the dracut resume module for hibernation" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q 'add_dracutmodules+=" resume "' "${RESUME_CONF}"
}

@test "packages-post: builds the initramfs for the last kernel rpm reported" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "--kver 6.12.9-100.el10.x86_64" "${CMD_LOG}"
    grep -q -- "${MODULES_DIR}/6.12.9-100.el10.x86_64/initramfs.img" "${CMD_LOG}"
}

@test "packages-post: dracut is invoked with ostree and reproducible flags" {
    patch_and_run
    [ "$status" -eq 0 ]
    line="$(grep "^dracut " "${CMD_LOG}" | head -1)"
    [[ "$line" == *"--no-hostonly"* ]]
    [[ "$line" == *"--reproducible"* ]]
    [[ "$line" == *"--add ostree"* ]]
}

@test "packages-post: does not match kernel-core when resolving the kernel version" {
    export STUB_RPM_QA="kernel-6.12.0-55.el10.x86_64
kernel-core-6.99.0-1.el10.x86_64"
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "--kver 6.12.0-55.el10.x86_64" "${CMD_LOG}"
}

@test "packages-post: runs depmod before dracut builds the initramfs" {
    patch_and_run
    [ "$status" -eq 0 ]
    depmod_at="$(cmd_line "depmod -a")"
    dracut_at="$(cmd_line "^dracut ")"
    [ -n "$depmod_at" ]
    [ -n "$dracut_at" ]
    [ "$depmod_at" -lt "$dracut_at" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Footguns and sudo path
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: removes the chsh and lchsh footguns" {
    patch_and_run
    [ "$status" -eq 0 ]
    [ ! -e "${TEST_ROOT}/usr/bin/chsh" ]
    [ ! -e "${TEST_ROOT}/usr/bin/lchsh" ]
}

@test "packages-post: appends linuxbrew to the sudo secure_path" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "secure_path = /usr/local/sbin:/usr/sbin:/usr/bin:/home/linuxbrew/.linuxbrew/bin" "${SUDOERS}"
}

@test "packages-post: leaves the rest of the sudoers file intact" {
    printf '# comment\nDefaults secure_path = /usr/bin\nDefaults env_reset\n' > "${SUDOERS}"
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "^# comment$" "${SUDOERS}"
    grep -q "^Defaults env_reset$" "${SUDOERS}"
}
