---
name: testing
description: >-
  Choose GitHub Actions unit, image-build, and end-to-end coverage when validating image or build-script changes.
---

# Testing — GitHub Actions

## When to Use

Use when validating build scripts, image content, or configuration files.

## When NOT to Use

Do not use this skill to change CI workflow design or release promotion policy.

## Common Rationalizations

- “A container test proves boot behavior.” Container tests do not establish boot behavior.

## Red Flags

- Testing only a mutable tag, skipping the affected variant, or treating a cached image as fresh evidence.

## GitHub Actions test suites

All automated image checks run in GitHub Actions:

| Change | Workflow |
|---|---|
| Shell and build-script behavior | `.github/workflows/unit-tests.yml` |
| Image builds | `.github/workflows/build-regular.yml`, `build-nvidia.yml` |
| PR system-files smoke coverage | `.github/workflows/pr-e2e.yml` |
| Shared end-to-end suite | `.github/workflows/run-testsuite.yml` |

`pr-e2e.yml` composes changed system files onto `bluefin-lts:testing`. Same-repository PRs publish that image to GHCR and invoke the smoke suite through `run-testsuite.yml`. Fork PRs receive no package-write credential, so the workflow currently cannot publish a composed image or invoke that cross-job smoke suite. Do not use `pull_request_target` for PR code; add a least-privilege same-job fork smoke path before treating fork coverage as equivalent.

For changes not covered by these paths, add or extend a GitHub Actions workflow. Keep checks scoped to affected paths and use the image built by the workflow.

For state-changing commands in container coverage, shadow them with test stubs before execution. Do not run `bootc switch` or `systemctl enable` in a container test.

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
      image: ghcr.io/thallium-suite/uranium:stable
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
            value: "ghcr.io/thallium-suite/uranium:stable"
      - name: legacy-hwe
        template: smoke
        arguments:
          parameters:
          - name: image
            value: "ghcr.io/ublue-os/bluefin:lts-hwe"
          - name: expected_target
            value: "ghcr.io/thallium-suite/uranium:stable"
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
are ~5 seconds. Use pinned tags (`:testing`, `:stable`) not `:latest` — floating tags
bypass the cache if the digest changes.

## KubeVirt VMs (full boot test)

Use the `lab-test` skill for full boot tests. Required when:
- Testing `bootc switch` end-to-end (staged → reboot → landed on new image)
- Testing actual systemd unit activation at boot
- Checking for failed units in the journal
- Any test requiring a running OS, not just a container

See: `~/.agents/skills/lab-test/SKILL.md`

## Verification

- Choose the smallest test layer that exercises the changed behavior.
- Record the image reference, source revision, command or workflow, and result.
- For boot, systemd, hardware, or `bootc switch` behavior, add or run dedicated GitHub Actions coverage; do not treat container success as proof of boot behavior.
