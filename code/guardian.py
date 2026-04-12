import os
import time
import sys
import winreg
import subprocess
import logging
import logging.handlers
import psutil

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
SCRIPT_PATH   = os.path.abspath(__file__)
LOG_FILE      = os.path.join(os.path.expanduser("~"), "fileguard.log")
CHECK_INTERVAL = 5          # secondes entre chaque vérification
MAX_LOG_MB    = 5

# Chemins des scripts à surveiller
# Si tu utilises des .exe (PyInstaller), remplace par les chemins des .exe
GUARDED_SCRIPTS = [
    os.path.join(os.path.dirname(SCRIPT_PATH), "file_watcher.py"),
    os.path.join(os.path.dirname(SCRIPT_PATH), "restorer.py"),
]
# ──────────────────────────────────────────────────────────────────────────────

_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=MAX_LOG_MB * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)


def install_autostart() -> None:
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    value = f'"{pythonw}" "{SCRIPT_PATH}"'
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0, winreg.KEY_SET_VALUE
    )
    winreg.SetValueEx(key, "FileGuard_Guardian", 0, winreg.REG_SZ, value)
    winreg.CloseKey(key)
    print(f"[+] Autostart installé : {value}")


def is_running(script: str) -> bool:
    """Vérifie si un script (ou exe) tourne déjà comme processus."""
    target = os.path.normcase(os.path.abspath(script))
    for proc in psutil.process_iter(["cmdline", "exe"]):
        try:
            # Vérifie les arguments de la ligne de commande
            cmdline = proc.info.get("cmdline") or []
            for arg in cmdline:
                if os.path.normcase(os.path.abspath(arg)) == target:
                    return True
            # Vérifie aussi le chemin de l'exe (pour les binaires PyInstaller)
            exe = proc.info.get("exe") or ""
            if exe and os.path.normcase(os.path.abspath(exe)) == target:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def launch(script: str) -> None:
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    # Support .exe PyInstaller : lance directement sans interpréteur
    if script.lower().endswith(".exe"):
        subprocess.Popen([script], creationflags=subprocess.DETACHED_PROCESS)
    else:
        subprocess.Popen(
            [pythonw, script],
            creationflags=subprocess.DETACHED_PROCESS
        )

    msg = f"[RELAUNCHED] {os.path.basename(script)}"
    print(msg)
    logging.warning(msg)


if __name__ == "__main__":
    if "--install" in sys.argv:
        install_autostart()
        sys.exit(0)

    logging.info(f"[START] Guardian actif — surveille {len(GUARDED_SCRIPTS)} processus")
    print(f"[*] FileGuard Guardian actif — intervalle : {CHECK_INTERVAL}s")

    while True:
        for script in GUARDED_SCRIPTS:
            if not is_running(script):
                logging.warning(f"[DOWN] '{os.path.basename(script)}' non détecté, relancement...")
                launch(script)
        time.sleep(CHECK_INTERVAL)