# Testing — ghost lab and podman headless

This file documents when and how to test changes in the ghost lab.
For cluster operations and KubeVirt VM tests, see the `lab-test` agent skill.

## Decision tree: VM vs. podman headless

| Question | Method |
|---|---|
| Does this script do the right thing inside the image? | Podman headless |
| Does the system boot correctly after this change? | KubeVirt VM |
| Is this package installed / available? | Podman headless |
| Does this systemd unit activate at boot? | KubeVirt VM |
| Is this config file present with correct content? | Podman headless |
| Does `bootc switch` land on the new image after reboot? | KubeVirt VM |
| Does this migration script detect variants correctly? | Podman headless |
| Are there failed units in the journal? | KubeVirt VM |

**Rule of thumb:** if the test can succeed inside a container with no boot, use podman
headless. It is 10-50x faster, cached, and repeatable.

## Podman headless via Argo (recommended)

Submit an Argo workflow that runs the actual image as a container directly.
No BIB disk build, no VM provisioning, no boot wait. Cached images run in ~5 seconds.

### When to use this

- Testing script logic, shell functions, case statement mappings
- Verifying a file exists / has correct content in the image
- Checking tool availability (`bootc`, `python3`, `systemctl`, `jq`)
- Validating config files (`/etc/containers/policy.json`, systemd unit syntax)
- Testing service or migration scripts against the real image environment
- Running the same check against multiple variants in parallel

### Workflow template

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: headless-smoke-
  namespace: argo
spec:
  entrypoint: run
  serviceAccountName: argo
  templates:
  - name: run
    container:
      image: ghcr.io/projectbluefin/bluefin-lts:stable
      command: [bash, -c]
      args:
      - |
        # Mock state-changing commands
        mkdir -p /tmp/bin
        cp /bin/true /tmp/bin/systemctl
        export PATH=/tmp/bin:$PATH

        PASS=0; FAIL=0

        check() {
          local desc="$1"; shift
          if "$@" >/dev/null 2>&1; then
            echo "PASS: $desc"; PASS=$((PASS+1))
          else
            echo "FAIL: $desc"; FAIL=$((FAIL+1))
          fi
        }

        check "python3 available"  command -v python3
        check "bootc available"    command -v bootc
        check "policy.json exists" test -f /etc/containers/policy.json

        echo "Results: $PASS passed, $FAIL failed"
        [ "$FAIL" -eq 0 ]
```

### Critical bash gotchas

- **Never use `set -e` with arithmetic counters.** `((PASS++))` when PASS=0 is falsy and
  exits. Use `PASS=$((PASS+1))` or `((++PASS))`.
- **JSON in heredocs, not printf with escaped quotes.** `printf '{"key": \"val\"}'` emits
  literal backslashes. Use a heredoc or `echo '{"key": "val"}'`.
- **Mock before running.** Put `/tmp/bin/` early in PATH so stubs shadow real binaries.
  Never let `bootc switch` or `systemctl enable` actually run in a container test.

### Multi-variant DAG

To test N variants in parallel, use a DAG with `inputs.parameters`:

```yaml
spec:
  entrypoint: matrix
  templates:
  - name: matrix
    dag:
      tasks:
      - name: base
        template: smoke
        arguments:
          parameters:
          - name: image
            value: "ghcr.io/ublue-os/bluefin:lts"
          - name: expected_target
            value: "ghcr.io/projectbluefin/bluefin-lts:stable"
      - name: legacy-hwe
        template: smoke
        arguments:
          parameters:
          - name: image
            value: "ghcr.io/ublue-os/bluefin:lts-hwe"
          - name: expected_target
            value: "ghcr.io/projectbluefin/bluefin-lts:stable"
  - name: smoke
    inputs:
      parameters:
      - name: image
      - name: expected_target
    container:
      image: "{{inputs.parameters.image}}"
      command: [bash, -c]
      args:
      - |
        expected="{{inputs.parameters.expected_target}}"
        # ... run checks
```

### Caching

Images are cached in the cluster after first pull. Subsequent runs of the same tag
are ~5 seconds. Use pinned tags (`:lts`, `:testing`) not `:latest` — floating tags
bypass the cache if the digest changes.

## Real example: lts-migration-smoke (2026-06-21)

Tested the `bluefin-lts-migrate` service logic across all 5 old-LTS variants.
All 5 tasks Succeeded in ~5 seconds each using cached images.

**What was proven:**
1. `python3` JSON parsing of `bootc status --format=json` works in the real old image
2. All variant → target mappings are correct (`bluefin-gdx` → `bluefin-lts-nvidia`, etc.)
3. Required tools (`python3`, `bootc`, `systemctl`) exist in `ghcr.io/ublue-os/bluefin:lts`
4. `/etc/motd.d/` is writable at container start
5. `/etc/containers/policy.json` has `insecureAcceptAnything` for `ghcr.io/projectbluefin`
   (meaning `bootc switch --enforce-container-sigpolicy` will succeed)

**Key finding on signing:** Both the old image (`ghcr.io/ublue-os/bluefin:lts`) and the
new image (`ghcr.io/projectbluefin/bluefin-lts:stable`) ship the same `policy.json` from
`projectbluefin/common`. The `ghcr.io/projectbluefin` registry is not listed explicitly
and falls through to the `""` catch-all (`insecureAcceptAnything`). The migration
`bootc switch --enforce-container-sigpolicy` call succeeds.

## KubeVirt VMs (full boot test)

Use the `lab-test` skill for full boot tests. Required when:
- Testing `bootc switch` end-to-end (staged → reboot → landed on new image)
- Testing actual systemd unit activation at boot
- Checking for failed units in the journal
- Any test requiring a running OS, not just a container

See: `~/.agents/skills/lab-test/SKILL.md`
