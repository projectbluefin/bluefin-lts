#!/usr/bin/env bats

# Unit tests for build_scripts/26-packages-post.sh
# Run with: bats tests/unit/packages_post_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
POST_SCRIPT="${SCRIPT_DIR}/../../build_scripts/26-packages-post.sh"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    CMD_LOG="${TEST_ROOT}/cmd.log"
    CURL_LOG="${TEST_ROOT}/curl.log"

    mkdir -p "${STUB_BIN}"
    mkdir -p "${TEST_ROOT}/usr/share/ublue-os"
    mkdir -p "${TEST_ROOT}/usr/share/glib-2.0/schemas"
    mkdir -p "${TEST_ROOT}/usr/share/doc/bluefin"
    mkdir -p "${TEST_ROOT}/etc/flatpak/remotes.d"
    mkdir -p "${TEST_ROOT}/usr/lib/systemd"
    mkdir -p "${TEST_ROOT}/usr/lib/firewalld/zones"
    mkdir -p "${TEST_ROOT}/etc/firewalld"
    mkdir -p "${TEST_ROOT}/etc/dracut.conf.d"
    mkdir -p "${TEST_ROOT}/lib/modules/6.12.0-100.el10.x86_64"
    mkdir -p "${TEST_ROOT}/usr/bin"

    # Initial file fixtures
    echo '{"icon": "󰣛"}' > "${TEST_ROOT}/usr/share/ublue-os/fastfetch.jsonc"
    echo '<schemalist><schema id="org.gnome.desktop.background"><key name="picture-uri" type="s"><default>"file:///usr/share/backgrounds/bluefin/bluefin-12.png"</default></key></schema></schemalist>' > "${TEST_ROOT}/usr/share/glib-2.0/schemas/zz0-bluefin-modifications.gschema.override"
    echo 'DefaultZone=public' > "${TEST_ROOT}/etc/firewalld/firewalld.conf"
    echo 'IPv6_rpfilter=strict' >> "${TEST_ROOT}/etc/firewalld/firewalld.conf"
    echo 'secure_path = /sbin:/bin:/usr/sbin:/usr/bin' > "${TEST_ROOT}/etc/sudoers"
    touch "${TEST_ROOT}/usr/bin/chsh" "${TEST_ROOT}/usr/bin/lchsh"

    # Generic command logging stubs
    for cmd in glib-compile-schemas gdk-pixbuf-query-loaders-64 ghcurl install depmod; do
        cat > "${STUB_BIN}/${cmd}" <<EOF
#!/usr/bin/env bash
echo "${cmd} \$*" >> "${CMD_LOG}"
exit 0
EOF
    done

    # dracut stub: assert options and log
    cat > "${STUB_BIN}/dracut" <<EOF
#!/usr/bin/env bash
echo "dracut \$*" >> "${CMD_LOG}"
exit 0
EOF

    # rpm stub: returns qualified kernel
    cat > "${STUB_BIN}/rpm" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == *"-qa"* ]]; then
    echo "kernel-6.12.0-100.el10.x86_64"
fi
exit 0
EOF

    # curl stub: handle file downloads matching expected patterns
    cat > "${STUB_BIN}/curl" <<EOF
#!/usr/bin/env bash
echo "curl \$*" >> "${CURL_LOG}"
echo "curl \$*" >> "${CMD_LOG}"
prev=""
for arg in "\$@"; do
    if [[ "\${prev}" == "-o" ]]; then
        if [[ "\${arg}" == *"zram-generator.conf" ]]; then
            echo "zram-size = min(ram / 2, 8192)" > "\${arg}"
        elif [[ "\${arg}" == *"FedoraWorkstation.xml" ]]; then
            echo '<port protocol="udp" port="1025-65535"/>' > "\${arg}"
        else
            echo "placeholder" > "\${arg}"
        fi
    fi
    prev="\${arg}"
done
exit 0
EOF

    chmod +x "${STUB_BIN}"/*
    export PATH="${STUB_BIN}:${PATH}"

    # Patch absolute paths to TEST_ROOT
    PATCHED_SCRIPT="${TEST_ROOT}/26-packages-post-patched.sh"
    sed \
        -e "s|/usr/share/ublue-os/fastfetch.jsonc|${TEST_ROOT}/usr/share/ublue-os/fastfetch.jsonc|g" \
        -e "s|/usr/share/glib-2.0/schemas|${TEST_ROOT}/usr/share/glib-2.0/schemas|g" \
        -e "s|/usr/share/doc/bluefin/|${TEST_ROOT}/usr/share/doc/bluefin/|g" \
        -e "s|/etc/flatpak/remotes.d|${TEST_ROOT}/etc/flatpak/remotes.d|g" \
        -e "s|/usr/lib/systemd/zram-generator.conf|${TEST_ROOT}/usr/lib/systemd/zram-generator.conf|g" \
        -e "s|/usr/lib/firewalld/zones/FedoraWorkstation.xml|${TEST_ROOT}/usr/lib/firewalld/zones/FedoraWorkstation.xml|g" \
        -e "s|/etc/firewalld/firewalld.conf|${TEST_ROOT}/etc/firewalld/firewalld.conf|g" \
        -e "s|/lib/modules/|${TEST_ROOT}/lib/modules/|g" \
        -e "s|/etc/dracut.conf.d/resume.conf|${TEST_ROOT}/etc/dracut.conf.d/resume.conf|g" \
        -e "s|/usr/bin/dracut|${STUB_BIN}/dracut|g" \
        -e "s|/usr/bin/chsh|${TEST_ROOT}/usr/bin/chsh|g" \
        -e "s|/usr/bin/lchsh|${TEST_ROOT}/usr/bin/lchsh|g" \
        -e "s|/etc/sudoers|${TEST_ROOT}/etc/sudoers|g" \
        "${POST_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"

    export PATCHED_SCRIPT TEST_ROOT STUB_BIN CMD_LOG CURL_LOG
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

run_script() {
    run bash "${PATCHED_SCRIPT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Happy path and error propagation
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: exits 0 on the happy path" {
    run_script
    [ "$status" -eq 0 ]
}

@test "packages-post: propagates download failure on zram-generator" {
    cat > "${STUB_BIN}/curl" <<EOF
#!/usr/bin/env bash
exit 1
EOF
    run_script
    [ "$status" -ne 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Branding and Fastfetch configuration
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: updates CentOS fastfetch icon" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "" "${TEST_ROOT}/usr/share/ublue-os/fastfetch.jsonc"
    ! grep -q "󰣛" "${TEST_ROOT}/usr/share/ublue-os/fastfetch.jsonc"
}

@test "packages-post: updates monthly wallpaper override and compiles glib schemas" {
    run_script
    [ "$status" -eq 0 ]
    local current_month
    current_month="$(date +%m)"
    grep -q "bluefin-${current_month}.png" "${TEST_ROOT}/usr/share/glib-2.0/schemas/zz0-bluefin-modifications.gschema.override"
    grep -q "glib-compile-schemas ${TEST_ROOT}/usr/share/glib-2.0/schemas" "${CMD_LOG}"
}

@test "packages-post: updates gdk-pixbuf loader cache" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "gdk-pixbuf-query-loaders-64 --update-cache" "${CMD_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Documentation & Flathub
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: downloads offline bluefin pdf documentation" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "ghcurl https://github.com/projectbluefin/documentation/releases/download/0.1/bluefin.pdf" "${CMD_LOG}"
    grep -q "install -Dm0644 -t ${TEST_ROOT}/usr/share/doc/bluefin/ /tmp/bluefin.pdf" "${CMD_LOG}"
}

@test "packages-post: adds Flathub repository" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "curl .*flathub.flatpakrepo" "${CMD_LOG}"
    [ -d "${TEST_ROOT}/etc/flatpak/remotes.d" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# System configs: zram & firewalld
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: installs zram-generator.conf from rawhide" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "zram-generator.conf" "${CURL_LOG}"
    [ -f "${TEST_ROOT}/usr/lib/systemd/zram-generator.conf" ]
}

@test "packages-post: configures FedoraWorkstation firewalld zone and loose rpfilter" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "DefaultZone=FedoraWorkstation" "${TEST_ROOT}/etc/firewalld/firewalld.conf"
    grep -q "IPv6_rpfilter=loose" "${TEST_ROOT}/etc/firewalld/firewalld.conf"
}

# ──────────────────────────────────────────────────────────────────────────────
# Kernel, modules & initramfs
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: runs depmod for latest kernel module directory" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "depmod -a 6.12.0-100.el10.x86_64" "${CMD_LOG}"
}

@test "packages-post: configures dracut resume module and builds ostree initramfs" {
    run_script
    [ "$status" -eq 0 ]
    grep -q 'add_dracutmodules+=" resume "' "${TEST_ROOT}/etc/dracut.conf.d/resume.conf"
    grep -q "dracut --no-hostonly --kver 6.12.0-100.el10.x86_64 --reproducible --tmpdir /boot --zstd -v --add ostree -f" "${CMD_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Security & Sudoers cleanups
# ──────────────────────────────────────────────────────────────────────────────

@test "packages-post: removes chsh and lchsh binaries" {
    run_script
    [ "$status" -eq 0 ]
    [ ! -f "${TEST_ROOT}/usr/bin/chsh" ]
    [ ! -f "${TEST_ROOT}/usr/bin/lchsh" ]
}

@test "packages-post: appends linuxbrew bin to secure_path in sudoers" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "secure_path = /sbin:/bin:/usr/sbin:/usr/bin:/home/linuxbrew/.linuxbrew/bin" "${TEST_ROOT}/etc/sudoers"
}
