# CLAUDE.md

Read [AGENTS.md](AGENTS.md) first: what this repository is, its design rules, and its layout.

- It never deletes experimental data and never writes into a DaVis project.
- Anything that must live in `AppData` (the storage registry) is set up by the user from their own
  shell -- an agent's sandbox can hide it from them (2026-09-20).
- The scheduled sync runs `python -m experimentkit` from a clone's working tree (an editable
  install, or `cd` into the repository): on a PC whose tasks run from this clone, an edit or a
  branch switch is what the next 10-minute sync runs. There, `storage sync`, `verify`, `pause`
  and `resume` act on the live drives; run them only when asked.
- Before committing: keep `pytest` green and add no new ruff findings in the files you touch
  (ruff is not yet clean; see AGENTS.md).

## The lab handbook

This lab follows the Lab Handbook: ../Lab-Code-Guide
Start at its `ONBOARDING.md`, read the one page for your role, and follow `conventions/` when
writing code and `practices/` before touching data or the rig. Anything specific to *this*
repository is above; the handbook covers everything else.

Send things back rather than editing it: keep the `lab-repo` block in this repository's
`AGENTS.md` current when capabilities change, and file a note for anything the handbook itself
should say —

    python "../Lab-Code-Guide/tools/note.py" --kind incident --repo . --title "..." --body "..." --share

(kinds: incident, proposal, drift, map, question)

`--share` commits and pushes that one note, so it reaches the maintainer from any machine. The
handbook's maintainer folds notes in. Apart from `--share`, never commit to the handbook from here.
