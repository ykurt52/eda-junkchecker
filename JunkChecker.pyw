"""JunkChecker launcher (double-click, or the PyInstaller entry point).

    JunkChecker.pyw [folder]                       open the window (and scan the folder)
    JunkChecker.pyw scan|clean|dupes|... [args]    command line, see junkchecker/cli.py
    JunkChecker.pyw --selftest <folder> [shot_dir] non-destructive UI smoke test
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CLI_COMMANDS = {"scan", "clean", "dupes", "restore-last", "stats", "gui", "--version", "-h", "--help"}

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == "--selftest":
        from junkchecker.ui.app import selftest
        print("\n".join(selftest(args[1], args[2] if len(args) > 2 else None)))
    elif args and args[0] in CLI_COMMANDS:
        from junkchecker.cli import main
        sys.exit(main(args) or 0)
    else:
        from junkchecker.ui.app import run
        run(args[0] if args else None)
