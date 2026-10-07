# Contributing

Thanks for helping! JunkChecker deliberately stays small and dependency-free.

## Ground rules

- **Never lose user data.** Anything that removes files must:
  - go through `junkchecker/actions.py`, which handles the Recycle Bin, archive or zip, history and undo;
  - ask for confirmation in the UI;
  - be logged.
- Mark a new rule `safe` only when the tool regenerates that file by itself. When in doubt use `unknown`.
- Do not add runtime dependencies. Use the standard library and tkinter only. Pillow is optional, for screenshots in the self-test.
- Every user-visible string goes into `junkchecker/i18n.py`. Add it in **both** `en` and `tr`; the test suite checks that the keys match.

## Project layout

```
JunkChecker.pyw            launcher (GUI, folder argument, --selftest)
junkchecker/
  default_rules.json       built-in rule profiles
  rules.py                 rule engine
  core.py                  scanner (excludes, keep-N, git-tracked, open-project protection, cancel)
  actions.py               recycle / move / zip and undo, Recycle Bin $I parser
  dupes.py                 duplicate finder
  gitutil.py report.py     Git helper, HTML/CSV export
  storage.py               settings, cache, log, history.jsonl
  platform_win.py          processes, file locks, drive types, reparse points
  cli.py __main__.py       command line
  shell_integration.py     Explorer context menu (HKCU)
  i18n.py                  strings
  ui/                      tkinter UI (app, theme, treemap, dialogs)
tests/                     unittest suite
tools/                     build and Task Scheduler scripts
```

## Adding a rule

Add the rule to a profile in `default_rules.json`; the schema is described in the README. Then add a case to `RulesTest.test_builtin` in `tests/test_junkchecker.py`.

## Checks before a pull request

```bat
python -m unittest discover -s tests -v
pythonw JunkChecker.pyw --selftest "<some folder>"   :: renders every tab in both languages and themes, deletes nothing
```

## Adding a language

Add a dict to `STRINGS` and an entry to `LANGS` in `i18n.py`. The language buttons in the header are created automatically.
