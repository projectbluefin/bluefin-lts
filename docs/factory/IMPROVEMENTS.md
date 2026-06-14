# Factory Improvements

Timeless record of meaningful improvements shipped to the factory pipeline.

---

- 2026-06-14: aligned Renovate/Mergeraptor automerge with factory pattern — `baseBranchPatterns: ["testing"]`, removed `base_branch: main` override, retargeted 3 stuck Mergeraptor PRs to `testing`; fixed dead promote triggers (`Testing Parity` → `Testing Gate`, `push: testing` → `push: main`) ([#218](https://github.com/projectbluefin/bluefin-lts/pull/218))
- 2026-06-14: added cosign verification for common/brew base images (keys/ + verify-container recipe, parity with bluefin); removed duplicate OEM hooks now shipped by common#672; added 27 bats unit tests for build scripts + 36 pytest tests for changelogs.py; all with CI workflows ([#219](https://github.com/projectbluefin/bluefin-lts/pull/219), [#220](https://github.com/projectbluefin/bluefin-lts/pull/220), [#221](https://github.com/projectbluefin/bluefin-lts/pull/221), [#222](https://github.com/projectbluefin/bluefin-lts/pull/222))
