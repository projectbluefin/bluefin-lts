# VM testing reference

`scripts/create-test-vm.sh` creates a bootable test VM with SSH access.

```bash
./scripts/create-test-vm.sh [VM_NAME] [IMAGE_TAG] [SSH_PUB_KEY]
```

Defaults are a local test name, the stable image tag, and
`$HOME/.ssh/id_ed25519.pub`.

Requirements: `podman`, `bootc`, `limactl`, QEMU, sudo, and an SSH key pair.
The script creates a local test image, a disk image under `/tmp`, and a Lima
configuration. Manage the VM with:

```bash
limactl start <VM_NAME>
limactl shell <VM_NAME>
limactl stop <VM_NAME>
limactl delete <VM_NAME>
```

Read the script before use; its arguments and generated paths are authoritative.
