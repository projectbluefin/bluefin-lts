# Glycin sandbox test profile

Based on [Moby's default profile at 2ceae35](https://github.com/moby/profiles/blob/2ceae35d351c156cb5a8efc0fdc4a08cf94569d8/seccomp/default.json), with explicit allowances for Bubblewrap's namespace setup syscalls.
The kernel still checks capabilities and namespace ownership. This applies only
inside Glycin build containers; no capabilities, devices, or privileged mode
are added. Sandbox tests remain enabled.

The canonical JSON SHA-256 of the unmodified upstream profile is
`2ebf3bdba229d3d972cfc3721001306de96cc5113a14b29cb510c2edd91ca84a`.
The upstream Apache-2.0 license is in seccomp-LICENSE.

The profile lives with the recipe so changes invalidate its published input digest.
