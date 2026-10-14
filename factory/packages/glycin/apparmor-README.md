# Glycin build AppArmor profile

`glycin.apparmor` renders Moby's default container profile from
[`moby/profiles@2ceae35d351c156cb5a8efc0fdc4a08cf94569d8`](https://github.com/moby/profiles/blob/2ceae35d351c156cb5a8efc0fdc4a08cf94569d8/apparmor/template.go),
using ABI 3.0, the standard global/base imports, and the recipe-specific name
`bluefin-factory-glycin`. The upstream Apache-2.0 license is preserved in
[`seccomp-LICENSE`](seccomp-LICENSE).

It changes only `deny mount` into permission for mount and pivot-root operations
needed by Bubblewrap. Container capabilities remain the engine defaults;
`CAP_SYS_ADMIN` is not added. Those operations therefore require the private
user namespace created by Bubblewrap. The default network, signal, ptrace,
`/proc`, and `/sys` restrictions remain intact. Regression tests reconstruct
and hash the rendered default after removing these two exceptions.

`container_policy.py load` loads the profile on AppArmor hosts before builds.
Both the stack workflow and reusable recipe builder select it for Glycin only.
The stack's namespace preflight uses the same policy before wave zero; hosts
without AppArmor still retain the recipe's syscall profile. Never substitute
an unconfined profile or disable the loader sandbox tests.
