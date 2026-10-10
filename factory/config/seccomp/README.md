# umockdev test syscall profile

This is Moby's default seccomp profile from [commit 2ceae35](https://github.com/moby/profiles/blob/2ceae35d351c156cb5a8efc0fdc4a08cf94569d8/seccomp/default.json), with one extra allow rule for `open_tree`.
Only umockdev builds use it. Its libc wrapper tests open existing paths with
flags zero; Docker otherwise blocks the syscall before the kernel can check
permissions. The kernel still checks capabilities for mount cloning. No
capabilities, device access, or privileged mode are added.

The unmodified profile's canonical JSON SHA-256 is `2ebf3bdba229d3d972cfc3721001306de96cc5113a14b29cb510c2edd91ca84a`.
The upstream Apache-2.0 license is included in LICENSE.
