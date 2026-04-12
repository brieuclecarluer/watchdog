import os
import time
import logging
import logging.handlers
import sys
import subprocess
import winreg
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
SCRIPT_PATH  = os.path.abspath(__file__)
LOG_FILE     = os.path.join(os.path.expanduser("~"), "fileguard.log")
SHUTDOWN_DELAY = 5          # secondes avant extinction
MAX_LOG_MB   = 5
# ──────────────────────────────────────────────────────────────────────────────

# Fichiers protégés : chemin absolu → contenu à restaurer
# Ajoute autant d'entrées que nécessaire
PROTECTED_FILES: dict[str, str] = {
    os.path.join(os.path.expanduser("~"), "Desktop", "READ_BEFORE_USING.txt"): (
        "🐻‍❄️ Before you use this PC to \"create\" with AI\n\n"
        "The polar bear on your wallpaper isn't decoration. It's looking at you like someone\n"
        "who already knows exactly what kind of nonsense you're about to try and who has\n"
        "absolutely zero patience left for half-baked schemes or shady shortcuts.\n\n"
        "Here's what it's trying to tell you, without sugarcoating anything:\n\n"
        "• Drop the delusions: Cranking out low-effort deepfakes isn't going to get you\n"
        "  anywhere in life. If you want real progress, learn things instead of cheating.\n\n"
        "• Respect privacy: If you're about to dump sensitive information here, think twice.\n\n"
        "• Put in actual effort: Misleading or sloppy content has never made anyone look smart.\n\n"
        "• Protect this machine: Stop downloading random stuff.\n\n"
        "• Have some ethics: If your goal is to manipulate or deceive, you're wasting your time.\n"
    ),
    # Ajoute d'autres fichiers protégés ici :
    # r"C:\path\to\other_protected_file.txt": "contenu...",
}

# Rotation automatique du log (partagé avec file_watcher)
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
    winreg.SetValueEx(key, "FileGuard_Restorer", 0, winreg.REG_SZ, value)
    winreg.CloseKey(key)
    print(f"[+] Autostart installé : {value}")


def shutdown(reason: str = "Fichier protégé supprimé") -> None:
    msg = f"[SHUTDOWN] {reason} — extinction dans {SHUTDOWN_DELAY}s"
    print(msg)
    logging.warning(msg)
    subprocess.run([
        "shutdown", "/s",
        "/t", str(SHUTDOWN_DELAY),
        "/c", f"{reason}. Extinction dans {SHUTDOWN_DELAY} secondes."
    ])


def restore_file(path: str) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(PROTECTED_FILES[path])
        msg = f"[RESTORED] {path}"
        print(msg)
        logging.warning(msg)
    except Exception as e:
        logging.error(f"[ERROR] restauration de '{path}' : {e}")


def ensure_all() -> None:
    """Restaure tous les fichiers protégés manquants au démarrage."""
    for path in PROTECTED_FILES:
        if not os.path.exists(path):
            logging.info(f"[MISSING] fichier protégé absent au démarrage, restauration : {path}")
            restore_file(path)


class RestoreHandler(FileSystemEventHandler):
    def on_deleted(self, event):
        path = event.src_path
        if path in PROTECTED_FILES:
            shutdown(reason=f"Fichier protégé supprimé : {os.path.basename(path)}")
            time.sleep(0.3)
            restore_file(path)

    def on_moved(self, event):
        # Couvre le cas où le fichier protégé est renommé/déplacé
        if event.src_path in PROTECTED_FILES:
            shutdown(reason=f"Fichier protégé déplacé : {os.path.basename(event.src_path)}")
            time.sleep(0.3)
            restore_file(event.src_path)


if __name__ == "__main__":
    if "--install" in sys.argv:
        install_autostart()
        sys.exit(0)

    ensure_all()
    logging.info(f"[START] Restorer actif — {len(PROTECTED_FILES)} fichier(s) protégé(s)")
    print(f"[*] FileGuard Restorer actif — {len(PROTECTED_FILES)} fichier(s) surveillé(s)")

    observer = Observer()
    watched_dirs = set(os.path.dirname(p) for p in PROTECTED_FILES)
    for d in watched_dirs:
        observer.schedule(RestoreHandler(), d, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("[STOP] Restorer arrêté manuellement")
    observer.join()