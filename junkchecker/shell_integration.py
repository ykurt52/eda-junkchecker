"""Explorer context menu ("Scan with JunkChecker") for folders, per user (HKCU, no admin needed).

    python -m junkchecker.shell_integration install
    python -m junkchecker.shell_integration uninstall
"""
import os, sys, winreg

KEYS = (r"Software\Classes\Directory\shell\JunkChecker", r"Software\Classes\Directory\Background\shell\JunkChecker")
LABEL = {"en": "Scan with JunkChecker", "tr": "JunkChecker ile tara"}


def launch_command(arg):
    if getattr(sys, "frozen", False):                      # PyInstaller exe
        return f'"{sys.executable}" "{arg}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "JunkChecker.pyw")
    return f'"{pyw}" "{script}" "{arg}"'


def install(lang="en"):
    for key, arg in zip(KEYS, ("%1", "%V")):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, LABEL.get(lang, LABEL["en"]))
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, sys.executable)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key + r"\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, launch_command(arg))


def uninstall():
    for key in KEYS:
        for sub in (key + r"\command", key):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, sub)
            except FileNotFoundError:
                pass


def is_installed():
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEYS[0]).Close()
        return True
    except OSError:
        return False


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "install":
        install(sys.argv[2] if len(sys.argv) > 2 else "en"); print("installed:", launch_command("%1"))
    elif cmd == "uninstall":
        uninstall(); print("removed")
    else:
        print(__doc__)
