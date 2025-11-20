Contributing to BackupSeeker
============================
Thank you for your interest in improving BackupSeeker. This guide covers issue reporting, proposing features, coding standards, plugin submissions, and review expectations.

Table of Contents
-----------------
1. Code of Conduct
2. Where to Start
3. Issue Workflow
4. Pull Request Guidelines
5. Development Environment
6. Coding Standards
7. Testing Strategy
8. Commit & Branch Conventions
9. Plugin Contributions
10. Backwards Compatibility
11. Security & Privacy
12. Attribution & Licensing
13. Release & Versioning

1. Code of Conduct
------------------
Be respectful, inclusive, and patient. Harassment, discrimination, or abusive behavior is not tolerated. (Add a `CODE_OF_CONDUCT.md` if the project grows.)

2. Where to Start
-----------------
- Look for issues labeled `good first issue` or `help wanted`.
- If unsure whether a change is desired, open a discussion issue first.

3. Issue Workflow
-----------------
- Provide context: problem statement, current behavior, desired behavior.
- Use labels: `bug`, `enhancement`, `plugins`, `ui`, `docs` as appropriate.
- Larger features: include a minimal design summary (impact, risks, alternatives).

4. Pull Request Guidelines
--------------------------
- Focus: a PR should address one logical change set.
- Description: summarize motivation, list major changes, note UI impacts.
- Screenshots/GIFs: include for UI changes.
- Checklist: confirm tests pass, docs updated, no unrelated refactors.
- Link issues: use `Closes #<id>` when applicable.

5. Development Environment
--------------------------
```pwsh
python -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
python -m pip install PyQt6
```
Run the app:
```pwsh
python -m BackupSeeker.main
```

6. Coding Standards
-------------------
- Style: follow PEP8; keep line length reasonable (~120 chars max).
- Typing: prefer type hints for public functions/classes.
- Imports: standard library first, then local modules; avoid unused imports.
- Docstrings: module, class, and public method docstrings clarify intent.
- Avoid emoji in code logic comments; UI labels may include minimal icons.

7. Testing Strategy
-------------------
- Core logic (`core.py`) can be unit tested (e.g., path contraction, backup/restore round‑trip to a temp folder).
- UI changes: manual test steps in PR description (expected labels, dialogs, theme behavior).
- Plugins: for complex hooks, add small tests simulating pre/post process dictionaries.

8. Commit & Branch Conventions
-------------------------------
- Branch names: `feature/<short-name>`, `fix/<issue-id>-<short>`, `docs/<short>`, `plugin/<game-id>`.
- Commit messages:
	- First line: imperative present tense (“Add backup retention option”).
	- Body: what & why (reference issue IDs).
- Squash trivial fixups before review when possible.

9. Plugin Contributions
-----------------------
- Keep `game_id` stable; never repurpose an existing id for a different game.
- Provide detection data: contracted `save_paths`, optional `registry_keys`.
- Hooks: only implement those you need; return input unchanged if not modifying.
- JSONC entries: ensure valid JSON after stripping `//` comments.
- Add test instructions (how to detect, expected folder) to the PR body.

10. Backwards Compatibility
---------------------------
- Changing profile schema: add migration logic or fallback handling.
- Renaming plugin IDs breaks existing profiles; introduce a new plugin instead.
- Deprecations: mark clearly in docs, keep for at least one minor release.

11. Security & Privacy
----------------------
- Backups can contain personal data; do not upload example backups.
- When adding future cloud sync features, document encryption and storage approach.
- Avoid collecting telemetry; if added, make it opt‑in and document clearly.

12. Attribution & Licensing
---------------------------
- Ensure the project has a `LICENSE` file (recommend MIT or Apache‑2.0).
- Attribute third-party code snippets in comments or a `NOTICE` file.

13. Release & Versioning
------------------------
- Suggested scheme: Semantic Versioning (`MAJOR.MINOR.PATCH`).
- Changelog: maintain `CHANGELOG.md` with categories: Added / Changed / Fixed / Deprecated / Removed / Security.
- Pre-release features behind flags or marked experimental until stable.

Questions?
----------
Open an issue with label `question` or start a discussion. Thank you for helping improve BackupSeeker.
