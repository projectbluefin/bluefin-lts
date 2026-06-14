# Factory Improvements

Timeless record of meaningful improvements shipped to the factory pipeline.

---

- 2026-06-14: aligned Renovate/Mergeraptor automerge with factory pattern — `baseBranchPatterns: ["testing"]`, removed `base_branch: main` override, retargeted 3 stuck Mergeraptor PRs to `testing`; fixed dead promote triggers (`Testing Parity` → `Testing Gate`, `push: testing` → `push: main`) ([#218](https://github.com/projectbluefin/bluefin-lts/pull/218))
