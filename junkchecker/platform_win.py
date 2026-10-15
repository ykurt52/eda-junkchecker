"""Small Windows helpers: running processes, file locks, drive types, reparse points."""
import ctypes, os, stat, subprocess

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DRIVE_REMOTE = 4

# executables of tools whose open projects we want to protect
EDA_PROCESSES = {"x2.exe": "Altium Designer", "circuitstudio.exe": "CircuitStudio",
                 "kicad.exe": "KiCad", "pcbnew.exe": "KiCad", "eeschema.exe": "KiCad", "freecad.exe": "FreeCAD"}


def set_app_id(app_id):
    """Give the process its own taskbar identity so Windows shows the app icon, not python's."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
    except Exception:
        pass


def running_eda_tools():
    """Return the set of EDA tool names currently running."""
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             creationflags=NO_WINDOW, timeout=10).stdout
    except Exception:
        return set()
    names = set()
    for line in out.splitlines():
        exe = line.split(",")[0].strip('"').lower()
        if exe in EDA_PROCESSES:
            names.add(EDA_PROCESSES[exe])
    return names


def is_locked(path):
    """True if another process holds the file open without sharing (e.g. an EDA tool)."""
    try:
        k32 = ctypes.windll.kernel32
        GENERIC_READ, OPEN_EXISTING, INVALID = 0x80000000, 3, ctypes.c_void_p(-1).value
        k32.CreateFileW.restype = ctypes.c_void_p
        h = k32.CreateFileW(str(path), GENERIC_READ, 0, None, OPEN_EXISTING, 0, None)
        if h == INVALID or h is None:
            return ctypes.GetLastError() in (32, 33)  # sharing / lock violation
        k32.CloseHandle(ctypes.c_void_p(h))
        return False
    except Exception:
        return False


def is_network_path(path):
    path = os.path.abspath(path)
    if path.startswith("\\\\"):
        return True
    try:
        root = os.path.splitdrive(path)[0] + "\\"
        return ctypes.windll.kernel32.GetDriveTypeW(root) == DRIVE_REMOTE
    except Exception:
        return False


def is_reparse_point(entry):
    """os.DirEntry -> True for symlinks / junctions (avoid loops and leaving the tree)."""
    try:
        if entry.is_symlink():
            return True
        st = entry.stat(follow_symlinks=False)
        return bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return True
