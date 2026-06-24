# Rename gdx → bluefin-lts-nvidia Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the `bluefin-gdx` image to `bluefin-lts-nvidia`, add a `:stable` floating alias for `:lts`, and file follow-on issues for branch rename consolidation and Nvidia code sharing across the factory.

**Architecture:** All changes are configuration/pipeline — no functional behaviour changes. The internal `ENABLE_GDX` build arg and `gdx` override directories are renamed to `ENABLE_NVIDIA`/`nvidia` throughout. The public image name on GHCR changes from `bluefin-gdx` to `bluefin-lts-nvidia`. A new `tag-stable` job in `execute-release.yml` creates `:stable` as a floating alias for `:lts` after every release using `skopeo copy`.

**Tech Stack:** GitHub Actions, Bash, Just (Justfile), actionlint, skopeo, git

---

## Nvidia Enablement Comparison

Before implementing, here is the current state across the factory (informing the follow-on issue):

| Component | bluefin-lts (gdx) | bluefin | dakota |
|---|---|---|---|
| Driver source | negativo17 repo (`fedora-nvidia.repo`) | ublue-os `nvidia-install.sh` from akmods bundle | BuildStream elements (`nvidia-drivers.bst`) |
| kmod source | `akmods-nvidia-open` bound into build | `akmods-nvidia-open` copied with skopeo | gnome-build-meta BST |
| CDI setup | `nvidia-container-toolkit` + config.toml + `ublue-nvctk-cdi.service` + SELinux module | `libnvidia-container` + `nvidia-ctk` + `kargs.d/00-nvidia.toml` | `nvidia-container-toolkit.bst` |
| kms-modifiers gschema | `40-overrides.sh` in `overrides/gdx/` | `00-image-info.sh` (gschemas) | BST element |
| Kernel args | `kargs.d/00-nvidia.toml` inline in `20-nvidia.sh` | `kargs.d/00-nvidia.toml` inline in `04-install-kernel-akmods.sh` | `nvidia-kargs.bst` |
| Flatpak sync service | Not applied (common ships it, but lts doesn't pull `system_files/nvidia/`) | `common/system_files/nvidia/ublue-nvidia-flatpak-runtime-sync.*` | N/A |
| VS Code Nsight | `30-gdx-vscode.sh` hook | Presumed similar | N/A |

**Identified sharing opportunities (follow-on issues):**
1. `kargs.d/00-nvidia.toml` content is near-identical between bluefin and bluefin-lts — candidate to move to `projectbluefin/common/system_files/nvidia/`
2. kms-modifiers gschema override duplicated independently in both repos — candidate for `common`
3. `common/system_files/nvidia/ublue-nvidia-flatpak-runtime-sync.*` is shipped by common but bluefin-lts does not apply it — should evaluate and enable if applicable
4. bluefin uses `nvidia-install.sh` (upstream-blessed, avoids negativo17) while bluefin-lts maintains its own install script — evaluate migrating lts to `nvidia-install.sh` for convergence

---

## File Map

| Action | File |
|---|---|
| `git mv` | `build_scripts/overrides/gdx/` → `build_scripts/overrides/nvidia/` |
| `git mv` | `system_files_overrides/gdx/` → `system_files_overrides/nvidia/` |
| `git mv` | `system_files_overrides/nvidia/usr/share/ublue-os/user-setup.hooks.d/30-gdx-vscode.sh` → `30-nvidia-vscode.sh` |
| `git mv` | `.github/workflows/build-gdx.yml` → `.github/workflows/build-nvidia.yml` |
| Modify | `Containerfile` — `ENABLE_GDX` → `ENABLE_NVIDIA` |
| Modify | `build_scripts/build.sh` — `ENABLE_GDX` / `gdx` directory references → `ENABLE_NVIDIA` / `nvidia` |
| Modify | `build_scripts/overrides/nvidia/90-image-info.sh` — `FLAVOR` + `IMAGE_NAME` |
| Modify | `system_files_overrides/nvidia/usr/share/ublue-os/user-setup.hooks.d/30-nvidia-vscode.sh` — version-script key |
| Modify | `Justfile` — `$gdx`/`ENABLE_GDX`/brand detection/comments → `$nvidia`/`ENABLE_NVIDIA`/`*nvidia*` |
| Modify | `.github/workflows/build-nvidia.yml` — `brand_name` |
| Modify | `.github/workflows/execute-release.yml` — `bluefin-gdx` references + new `tag-stable` job |
| Modify | `.github/workflows/promote-testing-to-main.yml` — matrix |
| Modify | `.github/workflows/pr-release-gate.yml` — matrix |
| Modify | `.github/changelog_config.yaml` — targets, patterns, section name |

---

## Task 1: Rename directories and workflow file

**Files:**
- `git mv build_scripts/overrides/gdx/ build_scripts/overrides/nvidia/`
- `git mv system_files_overrides/gdx/ system_files_overrides/nvidia/`
- `git mv system_files_overrides/nvidia/usr/share/ublue-os/user-setup.hooks.d/30-gdx-vscode.sh → 30-nvidia-vscode.sh`
- `git mv .github/workflows/build-gdx.yml .github/workflows/build-nvidia.yml`

- [ ] **Step 1: Rename build_scripts override directory**

```bash
cd /var/home/jorge/src/bluefin-lts
git mv build_scripts/overrides/gdx build_scripts/overrides/nvidia
```

- [ ] **Step 2: Rename system_files override directory**

```bash
git mv system_files_overrides/gdx system_files_overrides/nvidia
```

- [ ] **Step 3: Rename the VS Code hook file**

```bash
git mv system_files_overrides/nvidia/usr/share/ublue-os/user-setup.hooks.d/30-gdx-vscode.sh \
       system_files_overrides/nvidia/usr/share/ublue-os/user-setup.hooks.d/30-nvidia-vscode.sh
```

- [ ] **Step 4: Rename the build workflow file**

```bash
git mv .github/workflows/build-gdx.yml .github/workflows/build-nvidia.yml
```

- [ ] **Step 5: Verify renames**

```bash
git status --short | grep -E '^R'
```

Expected output (4 renames):
```
R  .github/workflows/build-gdx.yml -> .github/workflows/build-nvidia.yml
R  build_scripts/overrides/gdx/20-nvidia.sh -> build_scripts/overrides/nvidia/20-nvidia.sh
R  build_scripts/overrides/gdx/30-packages.sh -> build_scripts/overrides/nvidia/30-packages.sh
R  build_scripts/overrides/gdx/40-overrides.sh -> build_scripts/overrides/nvidia/40-overrides.sh
R  build_scripts/overrides/gdx/90-image-info.sh -> build_scripts/overrides/nvidia/90-image-info.sh
R  system_files_overrides/gdx/... -> system_files_overrides/nvidia/...
```

- [ ] **Step 6: Commit the renames**

```bash
git add -A
git commit -m "refactor: rename gdx directories and workflow to nvidia

Renames:
- build_scripts/overrides/gdx/ → build_scripts/overrides/nvidia/
- system_files_overrides/gdx/ → system_files_overrides/nvidia/
- .github/workflows/build-gdx.yml → .github/workflows/build-nvidia.yml
- 30-gdx-vscode.sh → 30-nvidia-vscode.sh

No content changes yet; followup commits update all internal references.

Assisted-by: Claude Sonnet 4.5 via pi"
```

---

## Task 2: Update build script and image-info references

**Files:**
- Modify: `Containerfile`
- Modify: `build_scripts/build.sh`
- Modify: `build_scripts/overrides/nvidia/90-image-info.sh`
- Modify: `system_files_overrides/nvidia/usr/share/ublue-os/user-setup.hooks.d/30-nvidia-vscode.sh`

- [ ] **Step 1: Update Containerfile — rename build arg**

In `Containerfile`, find line:
```
ARG ENABLE_GDX="${ENABLE_GDX:-0}"
```
Replace with:
```
ARG ENABLE_NVIDIA="${ENABLE_NVIDIA:-0}"
```

Verify:
```bash
grep -n 'ENABLE_GDX\|ENABLE_NVIDIA' Containerfile
```
Expected: only `ENABLE_NVIDIA` remains.

- [ ] **Step 2: Update build.sh — rename env var and directory references**

In `build_scripts/build.sh`, find the block (around line 63):
```bash
if [ "$ENABLE_GDX" == "1" ]; then
	copy_systemfiles_for gdx
	run_buildscripts_for gdx
	copy_systemfiles_for "$(arch)-gdx"
	run_buildscripts_for "$(arch)/gdx"
fi
```

Replace with:
```bash
if [ "$ENABLE_NVIDIA" == "1" ]; then
	copy_systemfiles_for nvidia
	run_buildscripts_for nvidia
	copy_systemfiles_for "$(arch)-nvidia"
	run_buildscripts_for "$(arch)/nvidia"
fi
```

Verify:
```bash
grep -n 'GDX\|gdx' build_scripts/build.sh
```
Expected: zero matches.

- [ ] **Step 3: Update 90-image-info.sh — rename FLAVOR and IMAGE_NAME**

Full content of `build_scripts/overrides/nvidia/90-image-info.sh` should be updated. Open the file and change:
```bash
FLAVOR="gdx"
```
to:
```bash
FLAVOR="nvidia"
```

And any line containing `IMAGE_NAME=bluefin-gdx` or `bluefin-gdx` in the IMAGE_REF construction to `bluefin-lts-nvidia`.

Verify:
```bash
grep -n 'gdx\|GDX' build_scripts/overrides/nvidia/90-image-info.sh
```
Expected: zero matches.

- [ ] **Step 4: Update 30-nvidia-vscode.sh — rename version-script key**

In `system_files_overrides/nvidia/usr/share/ublue-os/user-setup.hooks.d/30-nvidia-vscode.sh`, find:
```bash
version-script gdx-vscode-lts user 1 || exit 0
```
Replace with:
```bash
version-script nvidia-vscode-lts user 1 || exit 0
```

Verify:
```bash
grep -n 'gdx' system_files_overrides/nvidia/usr/share/ublue-os/user-setup.hooks.d/30-nvidia-vscode.sh
```
Expected: zero matches.

- [ ] **Step 5: Sanity-check — no remaining gdx references in build scripts**

```bash
grep -rn 'gdx\|GDX' build_scripts/ system_files_overrides/ Containerfile
```
Expected: zero matches.

- [ ] **Step 6: Commit**

```bash
git add Containerfile build_scripts/ system_files_overrides/
git commit -m "refactor: rename ENABLE_GDX → ENABLE_NVIDIA in build pipeline

- Containerfile: ARG ENABLE_GDX → ARG ENABLE_NVIDIA
- build.sh: ENABLE_GDX check + gdx directory paths → ENABLE_NVIDIA / nvidia
- 90-image-info.sh: FLAVOR=gdx → nvidia, IMAGE_NAME=bluefin-gdx → bluefin-lts-nvidia
- 30-nvidia-vscode.sh: version-script key gdx-vscode-lts → nvidia-vscode-lts

Assisted-by: Claude Sonnet 4.5 via pi"
```

---

## Task 3: Update Justfile

**Files:**
- Modify: `Justfile`

The Justfile has these gdx-related references to update:
1. `build` recipe parameter `$gdx` → `$nvidia`
2. `BUILD_ARGS+=("--build-arg" "ENABLE_GDX=${gdx}")` → `ENABLE_NVIDIA=${nvidia}`
3. The `hwe || gdx` akmods branch logic
4. `build-ghcr` recipe: `GDX=0` variable, `*"gdx"*` suffix detection
5. Comment lines referencing GDX, docs URL, description

- [ ] **Step 1: Update the `build` recipe signature and ENABLE_GDX arg**

In `Justfile`, find:
```
build $target_image=image_name $tag=default_tag $dx="0" $gdx="0" $hwe="0" $kernel_pin=""
```
Replace with:
```
build $target_image=image_name $tag=default_tag $dx="0" $nvidia="0" $hwe="0" $kernel_pin=""
```

Then find:
```
    BUILD_ARGS+=("--build-arg" "ENABLE_GDX=${gdx}")
```
Replace with:
```
    BUILD_ARGS+=("--build-arg" "ENABLE_NVIDIA=${nvidia}")
```

Then find the akmods condition:
```bash
    if [[ "${hwe}" -eq "1" || "${gdx}" -eq "1" ]]; then
```
Replace with:
```bash
    if [[ "${hwe}" -eq "1" || "${nvidia}" -eq "1" ]]; then
```

- [ ] **Step 2: Update the `build-ghcr` recipe**

Find in Justfile:
```bash
    HWE=0
    GDX=0
    [[ "{{ base }}" == *"-hwe"* ]] && HWE=1
    [[ "{{ base }}" == *"gdx"* ]] && GDX=1
    {{ just_executable() }} build "{{ base }}" "{{ stream }}" "0" "${GDX}" "${HWE}" "{{ kernel_pin }}"
```
Replace with:
```bash
    HWE=0
    NVIDIA=0
    [[ "{{ base }}" == *"-hwe"* ]] && HWE=1
    [[ "{{ base }}" == *"nvidia"* ]] && NVIDIA=1
    {{ just_executable() }} build "{{ base }}" "{{ stream }}" "0" "${NVIDIA}" "${HWE}" "{{ kernel_pin }}"
```

- [ ] **Step 3: Update help comments**

Find (around line 82-94):
```
#   $gdx - Enable GDX (default: "0").
```
Replace with:
```
#   $nvidia - Enable Nvidia drivers (default: "0").
```

Find:
```
# GDX: https://docs.projectbluefin.io/gdx/
# GPU Developer Experience (GDX) creates a base as an AI and Graphics platform.
# Installs Nvidia drivers, CUDA, and other tools.
```
Replace with:
```
# Nvidia: https://docs.projectbluefin.io/nvidia/
# Nvidia image creates a base as an AI and Graphics platform.
# Installs Nvidia drivers, CUDA, and other tools.
```

Find:
```
# just build $target_image $tag $dx $gdx $hwe
# Example usage:
# just build bluefin lts 1 0 1
# This will build an image 'bluefin:lts' with DX and HWE enabled.
```
Replace with:
```
# just build $target_image $tag $dx $nvidia $hwe
# Example usage:
# just build bluefin-lts-nvidia lts 0 1 0
# This will build an image 'bluefin-lts-nvidia:lts' with Nvidia drivers enabled.
```

- [ ] **Step 4: Update the comment on build-ghcr**

Find:
```
# Maps brand_name suffix to ENABLE_HWE / ENABLE_GDX build args.
```
Replace with:
```
# Maps brand_name suffix to ENABLE_HWE / ENABLE_NVIDIA build args.
```

- [ ] **Step 5: Verify no remaining gdx/GDX references**

```bash
grep -n 'gdx\|GDX' Justfile
```
Expected: zero matches.

- [ ] **Step 6: Commit**

```bash
git add Justfile
git commit -m "refactor: rename \$gdx → \$nvidia in Justfile

- build recipe: \$gdx → \$nvidia parameter
- ENABLE_GDX build arg → ENABLE_NVIDIA
- build-ghcr: GDX detection from *gdx* suffix → *nvidia* suffix
- Update help comments and example usage

Assisted-by: Claude Sonnet 4.5 via pi"
```

---

## Task 4: Update GitHub Actions workflows

**Files:**
- Modify: `.github/workflows/build-nvidia.yml`
- Modify: `.github/workflows/execute-release.yml`
- Modify: `.github/workflows/promote-testing-to-main.yml`
- Modify: `.github/workflows/pr-release-gate.yml`
- Modify: `.github/changelog_config.yaml`

- [ ] **Step 1: Update build-nvidia.yml — brand_name and workflow name**

In `.github/workflows/build-nvidia.yml`, make these changes:

```yaml
# Line 1: rename the workflow
name: Build Bluefin Nvidia   # was: Build Bluefin GDX

# In the build job inputs:
      brand_name: bluefin-lts-nvidia   # was: bluefin-gdx
```

Also update the job name:
```yaml
    name: Build bluefin-lts-nvidia image   # was: Build bluefin-gdx image
```

- [ ] **Step 2: Update execute-release.yml — image name and digests**

In `.github/workflows/execute-release.yml`, make these changes:

In the `execute` job variants:
```yaml
      variants: >-
        [
          {"image":"bluefin-lts","source_tag":"testing","target_tag":"lts"},
          {"image":"bluefin-lts-hwe","source_tag":"testing","target_tag":"lts"},
          {"image":"bluefin-lts-nvidia","source_tag":"testing","target_tag":"lts"}
        ]
```
(was `"bluefin-gdx"`)

In the `post-release-variants` job `digests` step:
```bash
          for image in bluefin-lts bluefin-lts-hwe bluefin-lts-nvidia; do
```
(was `bluefin-gdx`)

In the env block:
```yaml
          NVIDIA_DIGEST: ${{ steps.digests.outputs.bluefin-lts-nvidia }}
```
(was `GDX_DIGEST: ${{ steps.digests.outputs.bluefin-gdx }}`)

In the release notes printf:
```bash
            "| \`bluefin-lts-nvidia\` | \`:lts\` | \`${NVIDIA_DIGEST}\` |" \
```
(was `bluefin-gdx` / `GDX_DIGEST`)

In the footer note line:
```bash
            '> **bluefin-lts-hwe** and **bluefin-lts-nvidia** use the Fedora CoreOS stable kernel. The **Kernel (HWE)** version above applies to both.' \
```

- [ ] **Step 3: Update promote-testing-to-main.yml — image matrix**

Find:
```yaml
        [{"image":"bluefin-lts"},{"image":"bluefin-lts-hwe"},{"image":"bluefin-gdx"}]
```
Replace with:
```yaml
        [{"image":"bluefin-lts"},{"image":"bluefin-lts-hwe"},{"image":"bluefin-lts-nvidia"}]
```

- [ ] **Step 4: Update pr-release-gate.yml — image matrix**

Find:
```yaml
      variants: >-
        [{"image":"bluefin-lts"},{"image":"bluefin-lts-hwe"},{"image":"bluefin-gdx"}]
```
Replace with:
```yaml
      variants: >-
        [{"image":"bluefin-lts"},{"image":"bluefin-lts-hwe"},{"image":"bluefin-lts-nvidia"}]
```

- [ ] **Step 5: Update changelog_config.yaml**

Find:
```yaml
targets: ["lts", "dx", "gdx"]
```
Replace with:
```yaml
targets: ["lts", "dx", "nvidia"]
```

Find the pattern entry (around line 28):
```yaml
  - "-gdx"
```
Replace with:
```yaml
  - "-nvidia"
```

Find the section name entry (around line 109):
```yaml
  gdx: "[Graphical Developer Experience Images](https://docs.projectbluefin.io/gdx)"
```
Replace with:
```yaml
  nvidia: "[Nvidia Images](https://docs.projectbluefin.io/nvidia)"
```

- [ ] **Step 6: Verify no remaining gdx references in workflows or changelog config**

```bash
grep -rn 'gdx\|GDX\|bluefin-gdx' .github/
```
Expected: zero matches.

- [ ] **Step 7: Commit**

```bash
git add .github/
git commit -m "feat: rename bluefin-gdx → bluefin-lts-nvidia in all workflows

- build-nvidia.yml: brand_name bluefin-gdx → bluefin-lts-nvidia
- execute-release.yml: update variants, digests, release notes
- promote-testing-to-main.yml: update image matrix
- pr-release-gate.yml: update image matrix
- changelog_config.yaml: gdx → nvidia target, pattern, section

Assisted-by: Claude Sonnet 4.5 via pi"
```

---

## Task 5: Add :stable floating alias for :lts

**Files:**
- Modify: `.github/workflows/execute-release.yml`

The `:stable` tag should be a floating alias that always points to the same digest as `:lts`. It is added as a new job in `execute-release.yml` that runs after `execute` succeeds and after `post-release-variants` completes.

- [ ] **Step 1: Add tag-stable job to execute-release.yml**

In `.github/workflows/execute-release.yml`, after the `post-release-variants` job, add a new job:

```yaml
  tag-stable:
    # Create :stable as a floating alias for :lts on every release.
    # This makes it easier for users who prefer a stable-named tag.
    needs: [execute]
    if: always() && needs.execute.result == 'success'
    runs-on: ubuntu-latest
    permissions:
      packages: write
      id-token: write
    env:
      REGISTRY: ghcr.io/projectbluefin
    steps:
      - name: Install skopeo
        run: |
          sudo apt-get update -q
          sudo apt-get install -y skopeo

      - name: Copy :lts → :stable for all variants
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          echo "${{ secrets.GITHUB_TOKEN }}" | skopeo login ghcr.io \
            --username "${{ github.actor }}" --password-stdin

          for image in bluefin-lts bluefin-lts-hwe bluefin-lts-nvidia; do
            DIGEST=$(skopeo inspect --no-tags "docker://${REGISTRY}/${image}:lts" \
              | jq -r '.Digest')
            echo "Tagging ${image}@${DIGEST} as :stable"
            skopeo copy \
              "docker://${REGISTRY}/${image}@${DIGEST}" \
              "docker://${REGISTRY}/${image}:stable"
            echo "  ✅ ${image}:stable → ${image}@${DIGEST}"
          done
```

- [ ] **Step 2: Validate the workflow with actionlint**

```bash
actionlint .github/workflows/execute-release.yml
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/execute-release.yml
git commit -m "feat: add :stable floating alias for :lts on every release

After each release, skopeo-copies :lts → :stable for all three variants:
- bluefin-lts:stable
- bluefin-lts-hwe:stable
- bluefin-lts-nvidia:stable

This makes the production tag discoverable without knowing the lts
branch naming convention.

Assisted-by: Claude Sonnet 4.5 via pi"
```

---

## Task 6: Validate and lint the full change set

**Files:** All changed files.

- [ ] **Step 1: Run actionlint on all changed workflows**

```bash
actionlint .github/workflows/build-nvidia.yml \
           .github/workflows/execute-release.yml \
           .github/workflows/promote-testing-to-main.yml \
           .github/workflows/pr-release-gate.yml
```
Expected: no errors. Fix any reported issues before continuing.

- [ ] **Step 2: Run just check and just lint**

```bash
just check && just lint
```
Expected: passes. If `just lint` reports gdx references, fix them.

- [ ] **Step 3: Verify zero remaining gdx references across the repo**

```bash
grep -rn 'gdx\|GDX\|bluefin-gdx' \
  .github/ Containerfile build_scripts/ system_files_overrides/ Justfile \
  --include='*.yml' --include='*.yaml' --include='*.sh' --include='*.just' \
  --include='Justfile' --include='Containerfile'
```
Expected: zero matches.

- [ ] **Step 4: Dry-run local build with new name (optional but recommended)**

This takes ~45-90 min; skip if CI will cover it. Only run if you have a local Podman environment:
```bash
just build bluefin-lts-nvidia lts 0 1 0
```
Expected: builds without error, `IMAGE_NAME=bluefin-lts-nvidia` visible in output.

---

## Task 7: File follow-on issues on GitHub

**Files:** None (GitHub issues).

Two follow-on issues to file against `projectbluefin/bluefin-lts`:

### Issue A: Branch rename consolidation

**Title:** `chore: rename gdx branch reference to nvidia (post-image-rename consolidation)`

**Body:**
```markdown
## Context

The `bluefin-gdx` image was renamed to `bluefin-lts-nvidia` in [PR #XXX].
This follow-on issue tracks any remaining branch-level or git-tag-level references
that can now be cleaned up.

## Scope

- [ ] Evaluate whether a `gdx` git branch exists and needs a `nvidia` counterpart or redirect
- [ ] Update any existing git tags or releases that reference `bluefin-gdx` to add `bluefin-lts-nvidia` aliases
- [ ] Update docs/website references from `bluefin-gdx` to `bluefin-lts-nvidia`
- [ ] Update the bonedigger template sync if it references `gdx`
- [ ] Check if the `testsuite` repo references `bluefin-gdx` by name in any test matrix

## Floating tag approach (interim)

Until this is completed, the `:stable` alias added in the rename PR provides
the additional discoverability. The `bluefin-gdx` name on GHCR will stop
receiving new builds after the rename PR merges.
```

### Issue B: Nvidia enablement convergence across the factory

**Title:** `chore: converge Nvidia enablement code across bluefin, bluefin-lts, and common`

**Body:**
```markdown
## Context

During the gdx→nvidia rename we audited Nvidia enablement across the factory.
Several patterns are independently maintained that could be unified through
`projectbluefin/common`.

## Identified opportunities

### 1. kargs.d/00-nvidia.toml duplication
- **bluefin:** `build_files/base/04-install-kernel-akmods.sh` writes `kargs.d/00-nvidia.toml` inline
- **bluefin-lts:** `build_scripts/overrides/nvidia/20-nvidia.sh` writes the same file inline
- **Proposal:** move to `common/system_files/nvidia/usr/lib/bootc/kargs.d/00-nvidia.toml` and ship from common

### 2. kms-modifiers gschema override duplication
- **bluefin:** `build_files/base/00-image-info.sh` adds kms-modifiers gschema override
- **bluefin-lts:** `build_scripts/overrides/nvidia/40-overrides.sh` does the same
- **Proposal:** ship from `common/system_files/nvidia/` or merge the override into a shared script

### 3. common/system_files/nvidia/ not applied by bluefin-lts
- `projectbluefin/common` ships `ublue-nvidia-flatpak-runtime-sync.{service,script}` in `system_files/nvidia/`
- bluefin-lts **does not** currently apply these files
- **Proposal:** evaluate if these should be applied in `build_scripts/overrides/nvidia/`

### 4. nvidia-install.sh convergence
- **bluefin** uses the upstream-blessed `nvidia-install.sh` from the akmods RPM bundle
- **bluefin-lts** maintains its own `20-nvidia.sh` with a manual negativo17 repo setup
- **Proposal:** evaluate migrating bluefin-lts to `nvidia-install.sh` for lower maintenance burden
  (Note: CentOS Stream base may require adjustments vs Fedora)

## Non-goals

- Dakota uses BuildStream; its Nvidia path is intentionally different and not a target for convergence
```

- [ ] **Step 1: File Issue A (branch rename consolidation)**

```bash
gh issue create \
  --repo projectbluefin/bluefin-lts \
  --title "chore: rename gdx branch reference to nvidia (post-image-rename consolidation)" \
  --label "needs-triage" \
  --body "$(cat <<'EOF'
## Context

The `bluefin-gdx` image was renamed to `bluefin-lts-nvidia`. This follow-on issue
tracks branch-level cleanup.

## Scope

- [ ] Evaluate whether a `gdx` git branch exists and needs a `nvidia` counterpart or redirect
- [ ] Update any git tags or releases that reference `bluefin-gdx` to add `bluefin-lts-nvidia` aliases
- [ ] Update docs/website references from `bluefin-gdx` to `bluefin-lts-nvidia`
- [ ] Check if `testsuite` repo references `bluefin-gdx` by name in any test matrix

## Interim

The `:stable` alias added in the rename PR provides discoverability.
The `bluefin-gdx` name on GHCR stops receiving new builds after the rename PR merges.
EOF
)"
```

- [ ] **Step 2: File Issue B (Nvidia convergence)**

```bash
gh issue create \
  --repo projectbluefin/bluefin-lts \
  --title "chore: converge Nvidia enablement code across bluefin, bluefin-lts, and common" \
  --label "needs-triage" \
  --body "$(cat <<'EOF'
## Context

Audit during gdx→nvidia rename identified duplicated Nvidia patterns across the factory.

## Opportunities

**1. kargs.d/00-nvidia.toml duplication**
- Both bluefin and bluefin-lts write identical `kargs.d/00-nvidia.toml` content inline in their build scripts
- Proposal: move to `common/system_files/nvidia/usr/lib/bootc/kargs.d/00-nvidia.toml`

**2. kms-modifiers gschema override duplication**
- Both repos independently add the kms-modifiers gschema override for Nvidia builds
- Proposal: consolidate into `common/system_files/nvidia/`

**3. common/system_files/nvidia/ not applied by bluefin-lts**
- common ships `ublue-nvidia-flatpak-runtime-sync.*` in `system_files/nvidia/`
- bluefin-lts does not currently apply these
- Evaluate and enable if applicable

**4. nvidia-install.sh convergence**
- bluefin uses upstream `nvidia-install.sh` from the akmods bundle
- bluefin-lts maintains its own `20-nvidia.sh` with manual negativo17 repo setup
- Evaluate migrating bluefin-lts to `nvidia-install.sh` for lower maintenance burden

## Non-goals

Dakota uses BuildStream and is not a target for convergence.
EOF
)"
```

- [ ] **Step 3: Note issue numbers in the PR description**

After filing, capture the issue numbers and reference them in the PR body:
```
Follow-on: #<branch-rename-issue>
Follow-on: #<nvidia-convergence-issue>
```

---

## Task 8: Open the PR

- [ ] **Step 1: Verify branch is up to date**

```bash
git fetch origin main
git rebase origin/main
```

- [ ] **Step 2: Push the branch**

```bash
git push origin HEAD
```

- [ ] **Step 3: Open the PR**

```bash
gh pr create \
  --title "feat: rename bluefin-gdx to bluefin-lts-nvidia, add :stable alias" \
  --base main \
  --body "$(cat <<'EOF'
## Summary

Renames the Nvidia-enabled image from `bluefin-gdx` to `bluefin-lts-nvidia` to reflect
that a dedicated GDX image no longer makes sense now that the CUDA stack is moving to
containers for all Bluefins.

Also adds a `:stable` floating tag that mirrors `:lts` after each release for
easier discoverability.

## Changes

### Image rename: `bluefin-gdx` → `bluefin-lts-nvidia`
- `build_scripts/overrides/gdx/` → `build_scripts/overrides/nvidia/`
- `system_files_overrides/gdx/` → `system_files_overrides/nvidia/`
- `Containerfile`: `ENABLE_GDX` → `ENABLE_NVIDIA`
- `build.sh`: gdx directory paths → nvidia
- `Justfile`: `$gdx` param → `$nvidia`, `GDX` detection → `nvidia` suffix
- All GitHub Actions workflows updated

### `:stable` alias
- `execute-release.yml`: new `tag-stable` job after `execute` that skopeo-copies
  `:lts` → `:stable` for all three variants on every release

## Follow-on issues
- #<branch-rename-issue> — branch/tag cleanup
- #<nvidia-convergence-issue> — Nvidia code convergence across factory repos

## Testing
- [ ] actionlint passes on all changed workflows
- [ ] `just check && just lint` passes
- [ ] CI build completes with new `bluefin-lts-nvidia` image name
EOF
)"
```

---

## Self-Review

### Spec coverage

| Requirement | Task |
|---|---|
| Rename gdx → bluefin-lts-nvidia | Tasks 1–4 |
| :testing and :lts tags work for new name | Task 4 (workflows updated) |
| :stable alias for :lts | Task 5 |
| Follow-on issue for branch rename | Task 7 Issue A |
| Compare Nvidia enablement across repos | Comparison table + Task 7 Issue B |
| Find sharing opportunities | Task 7 Issue B |

### Placeholder scan

No TBDs, TODOs, or "implement later" present. All code blocks are complete.

### Type consistency

- `$nvidia` / `ENABLE_NVIDIA` / `NVIDIA=0` / `*nvidia*` — consistent throughout
- `bluefin-lts-nvidia` — consistent as the GHCR image name
- `nvidia` — consistent as the override directory name and FLAVOR value
