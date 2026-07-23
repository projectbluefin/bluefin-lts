#!/usr/bin/env bash
# Apple Silicon (M1/M2, Asahi Linux) support for Bluefin LTS.
#
# Ported from the proven tuna-os/tunaOS EL10 asahi overlay (2026-07-23,
# first promoted image passed the 35-point Asahi verify harness). Full
# stack from three sources:
#   CentOS Hyperscale SIG packages-asahi — kernel-16k, dracut-asahi,
#     update-m1n1, asahi-scripts/-fwupdate/-battery, linux-firmware-vendor,
#     asahi-platform-metapackage-{core,audio}
#   EPEL10 — m1n1, asahi-audio, alsa-ucm-asahi, speakersafetyd
#   @asahi/u-boot COPR (epel-10-aarch64) — uboot-images-armv8 with the
#     apple_m1 payload update-m1n1 hard-requires (in no EL repo yet)
# Still unpackaged for EL10: tiny-dfr (Touch Bar; best-effort).
#
# aarch64 only; no ISO path (Apple Silicon cannot external-boot — installs
# go through the asahi-installer flow, tuna-os/bootc-installer-asahi).
set -xeuo pipefail

if [ "$(uname -m)" != "aarch64" ]; then
	echo "ERROR: the asahi flavor only applies to aarch64 builds" >&2
	exit 1
fi

install_best_effort() {
	for pkg in "$@"; do
		dnf -y install "$pkg" || echo "WARNING: asahi package unavailable on EL10: $pkg"
	done
}

KEY=/etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-SIG-HyperScale
if [ ! -f "$KEY" ]; then
	curl -fsSL "https://www.centos.org/keys/RPM-GPG-KEY-CentOS-SIG-HyperScale" -o "$KEY"
fi
for repo in packages-main packages-asahi; do
	cat >"/etc/yum.repos.d/hyperscale-${repo}.repo" <<-EOF
		[hyperscale-${repo}]
		name=CentOS Hyperscale SIG - ${repo}
		baseurl=https://mirror.stream.centos.org/SIGs/10-stream/hyperscale/\$basearch/${repo}/
		enabled=1
		gpgcheck=1
		gpgkey=file://${KEY}
	EOF
done

# EPEL is enabled by the base package script; make sure anyway (m1n1 + the
# audio stack resolve from there).
rpm -q epel-release >/dev/null 2>&1 || dnf -y install epel-release || true

COPR_UBOOT="https://download.copr.fedorainfracloud.org/results/@asahi/u-boot"
cat >/etc/yum.repos.d/asahi-u-boot-copr.repo <<-EOF
	[copr-asahi-u-boot]
	name=Copr @asahi/u-boot (apple_m1 uboot-images-armv8 for EL10)
	baseurl=${COPR_UBOOT}/epel-10-\$basearch/
	enabled=1
	gpgcheck=1
	gpgkey=${COPR_UBOOT}/pubkey.gpg
EOF

# Swap the stock 4K kernel for the SIG's 16K asahi build.
dnf -y remove --no-autoremove kernel kernel-core kernel-modules \
	kernel-modules-core kernel-modules-extra || true
# metapackage-core pulls kernel-16k, dracut-asahi, update-m1n1 (-> m1n1 +
# uboot-images-armv8), alsa-ucm-asahi, asahi-fwupdate.
dnf -y install kernel-16k kernel-16k-modules-extra \
	asahi-platform-metapackage-core
install_best_effort \
	asahi-platform-metapackage-audio asahi-scripts \
	linux-firmware-vendor asahi-battery tiny-dfr

# ── Verification + staging ───────────────────────────────────────────────────
KVER=$(find /usr/lib/modules -maxdepth 1 -mindepth 1 -type d | sort -V | tail -1 | xargs basename)
case "$KVER" in
*asahi* | *16k*) ;;
*)
	echo "ERROR: newest kernel '${KVER}' is not an asahi/16k build" >&2
	exit 1
	;;
esac
# EL kernel RPMs stage vmlinuz + dtb/ in the modules tree natively; assert
# rather than stage (/boot is a tmpfs in this build).
[ -f "/usr/lib/modules/${KVER}/vmlinuz" ] || {
	echo "ERROR: no vmlinuz staged in /usr/lib/modules/${KVER}" >&2
	exit 1
}
ls "/usr/lib/modules/${KVER}/dtb/apple/" >/dev/null 2>&1 || {
	echo "ERROR: no Apple DTBs in /usr/lib/modules/${KVER}/dtb" >&2
	exit 1
}

# dracut-asahi ships the ESP vendor-firmware modules; make sure the config
# actually includes them, then rebuild the initramfs (package posttrans does
# not reliably run dracut in container builds).
if ! grep -rqs "asahi-firmware" /usr/lib/dracut/dracut.conf.d/ /etc/dracut.conf.d/ 2>/dev/null; then
	printf 'add_dracutmodules+=" asahi-firmware kernel-modules-asahi "\n' \
		>/usr/lib/dracut/dracut.conf.d/10-asahi.conf
fi
dracut --force --no-hostonly --reproducible \
	--kver "${KVER}" "/usr/lib/modules/${KVER}/initramfs.img"

# ── boot.bin lifecycle on bootc ──────────────────────────────────────────────
# bootc deploys never run package scriptlets, so update-m1n1 never re-runs
# after `bootc upgrade` — new DTBs/m1n1/U-Boot would silently never reach
# <ESP>/m1n1/boot.bin. Apple-DT-gated oneshot; no-ops off Apple hardware.
BOOTBIN_SYNC_REF=b263b74083d8000736aef7fbb2bf20e610ebbca0
BASE_URL="https://raw.githubusercontent.com/tuna-os/bootc-installer-asahi/${BOOTBIN_SYNC_REF}/components/asahi-bootbin-sync"
install -d /usr/libexec /usr/lib/systemd/system /usr/lib/systemd/system-preset
curl -fsSL "${BASE_URL}/asahi-bootbin-sync.sh" -o /usr/libexec/asahi-bootbin-sync
chmod 0755 /usr/libexec/asahi-bootbin-sync
curl -fsSL "${BASE_URL}/asahi-bootbin-sync.service" \
	-o /usr/lib/systemd/system/asahi-bootbin-sync.service
grep -q "ExecStart=/usr/libexec/asahi-bootbin-sync" \
	/usr/lib/systemd/system/asahi-bootbin-sync.service
printf 'enable asahi-bootbin-sync.service\n' \
	>/usr/lib/systemd/system-preset/90-asahi-bootbin-sync.preset
install -d /usr/lib/systemd/system/multi-user.target.wants
ln -sf ../asahi-bootbin-sync.service \
	/usr/lib/systemd/system/multi-user.target.wants/asahi-bootbin-sync.service

dnf clean all
