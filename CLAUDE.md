# CLAUDE.md

Read [AGENTS.md](AGENTS.md) first: what this repository is, its design rules, and its layout.

- It never deletes experimental data and never writes into a DaVis project.
- Anything that must live in `AppData` (the storage registry) is set up by the user from their own
  shell -- an agent's sandbox can hide it from them (2026-09-20).
- Before committing: `pytest && ruff check . && ruff format --check .`

## The lab handbook

This lab follows the Lab Handbook: C:/Users/LaVision/Documents/GitHub/Lab-Code-Guide
Start at its `ONBOARDING.md`, read the one page for your role, and follow `conventions/` when
writing code and `practices/` before touching data or the rig. Anything specific to *this*
repository is above; the handbook covers everything else.

Send things back rather than editing it: keep the `lab-repo` block in this repository's
`AGENTS.md` current when capabilities change, and file a note for anything the handbook itself
should say —

    python "C:/Users/LaVision/Documents/GitHub/Lab-Code-Guide/tools/note.py" --kind incident --repo . --title "..." --body "..."

(kinds: incident, proposal, drift, map, question)

The handbook's maintainer folds notes in. Never commit to the handbook from here.
