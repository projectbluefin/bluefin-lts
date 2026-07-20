# Skills

Load this file after [`AGENTS.md`](../../AGENTS.md). Load only the skill that
matches the task; supporting references are loaded on demand.

| Task | Skill |
|---|---|
| Build or validate an image locally | [`build`](build/SKILL.md) |
| Choose or change packages | [`packages`](packages/SKILL.md) |
| Resolve platform package differences | [`centos-vs-fedora`](centos-vs-fedora/SKILL.md) |
| Change or debug CI workflows | [`ci-cd`](ci-cd/SKILL.md) |
| Add or remove desktop extensions | [`gnome-extensions`](gnome-extensions/SKILL.md) |
| Change hardware integration | [`hardware`](hardware/SKILL.md) |
| Test build or image changes | [`testing`](testing/SKILL.md) |
| Verify, promote, or roll back artifacts | [`release`](release/SKILL.md) |
| Diagnose documentation-to-code drift | [`skill-drift`](skill-drift/SKILL.md) |
| Add or refactor a skill | [`skill-improvement`](skill-improvement/SKILL.md) |

## Loading rules

- Load one task skill first; follow its links only when needed.
- Load files under `references/` only for the procedure that requires them.
- Treat source files and workflows as authoritative when documentation conflicts.
- Keep durable rules in the canonical skill and link to them elsewhere.
- Avoid loading unrelated skills or complete workflow listings.

## Authoring rules

- Skill directories use lowercase kebab-case.
- Each skill entry is `SKILL.md` with only `name` and `description` front matter.
- Keep entry files under 500 lines; move optional detail to references.
- Use one canonical owner for each fact.
- Do not add dated status, session logs, resolved issue lists, or duplicate policy.
- Update this index whenever a skill is added, renamed, or retired.
