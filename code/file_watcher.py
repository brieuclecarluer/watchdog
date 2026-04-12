import os
import re
import time
import shutil
import logging
import logging.handlers
import sys
import winreg
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
WATCH_FOLDER = os.path.expanduser(r"~")          # Dossier surveillé (~ = home user)
LOG_FILE     = os.path.join(os.path.expanduser("~"), "fileguard.log")
SCRIPT_PATH  = os.path.abspath(__file__)
MAX_LOG_MB   = 5                                  # Rotation log à 5 MB
# ──────────────────────────────────────────────────────────────────────────────

BANNED_WORDS = [
    # ── Ransomware ──────────────────────────────────────────────────────────
    "wannacry", "wannacrypt", "petya", "notpetya", "locky", "ryuk", "revil",
    "darkside", "conti", "lockbit", "blackcat", "alphv", "maze", "sodinokibi",
    "gandcrab", "cerber", "cryptolocker", "cryptowall", "badrabbit", "samsa",
    "clop", "hive", "ragnarok", "netwalker", "egregor", "avaddon",
    # ── RATs / Stealers ─────────────────────────────────────────────────────
    "njrat", "darkcomet", "asyncrat", "quasar", "remcos", "nanocore",
    "xtremerat", "cybergate", "pandabanker", "emotet", "trickbot", "dridex",
    "agent tesla", "agent_tesla", "formbook", "azorult", "hawkeye", "loki",
    "raccoon", "redline", "vidar", "arkei", "warzone",
    # ── C2 Frameworks / Offensive tools ─────────────────────────────────────
    "metasploit", "msfvenom", "msfconsole", "cobalt strike", "cobaltstrike",
    "empire", "powersploit", "mimikatz", "meterpreter", "shellter",
    "veil", "unicorn", "pupy", "havoc", "brute ratel", "bruteratel", "sliver",
    # ── Spyware / Stalkerware ────────────────────────────────────────────────
    "stalkerware", "pegasus", "finspy", "darkspy",
    # ── Bootkits / Rootkits ──────────────────────────────────────────────────
    "bootkit", "necurs", "rustock", "tdss", "zeroaccess",
    # ── Botnets / Worms ──────────────────────────────────────────────────────
    "mirai", "conficker", "stuxnet", "flame", "regin", "sality",
    "zeus", "gameover", "blackenergy", "industroyer", "triton",
    # ── Offensive recon / cracking ───────────────────────────────────────────
    "nmap_scan", "masscan", "zmap", "sqlmap", "hydra_brute",
    "aircrack", "hashcat", "johntheripper", "john_the_ripper",
    # ── Web shells / Backdoors ───────────────────────────────────────────────
    "netcat_backdoor", "weevely", "webshell", "c99shell", "r57shell",
    "b374k", "antsword", "chopper",
    # ── Generic threat keywords ──────────────────────────────────────────────
    "malware", "ransomware", "exploit", "payload", "shellcode", "backdoor",
    "rootkit", "keylogger", "spyware", "trojan", "dropper",
    "crypter", "bypass_av", "antivirus_bypass",
]

# Compile une seule regex pour toutes les détections — plus efficace qu'une boucle
BANNED_PATTERN = re.compile(
    r"(" + "|".join(re.escape(w) for w in BANNED_WORDS) + r")",
    re.IGNORECASE
)

# Rotation automatique du log (5 MB max, 3 backups)
_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=MAX_LOG_MB * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)


def install_autostart():
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable          # fallback si pythonw absent
    value = f'"{pythonw}" "{SCRIPT_PATH}"'
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0, winreg.KEY_SET_VALUE
    )
    winreg.SetValueEx(key, "FileGuard_Watcher", 0, winreg.REG_SZ, value)
    winreg.CloseKey(key)
    print(f"[+] Autostart installé : {value}")


def is_banned(path: str) -> tuple[bool, str]:
    name = os.path.basename(path)
    match = BANNED_PATTERN.search(name)
    if match:
        return True, match.group(0)
    return False, ""


def delete_target(path: str) -> None:
    for attempt in range(3):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
            else:
                return
            msg = f"[DELETED] {path}"
            print(msg)
            logging.warning(msg)
            return
        except PermissionError:
            time.sleep(0.3 * (attempt + 1))    # backoff progressif
        except Exception as e:
            logging.error(f"[ERROR] suppression de '{path}' : {e}")
            return


class BanHandler(FileSystemEventHandler):
    def _check(self, path: str) -> None:
        banned, word = is_banned(path)
        if banned:
            logging.info(f"[DETECTED] '{os.path.basename(path)}' — mot banni : '{word}'")
            delete_target(path)

    def on_created(self, event):
        self._check(event.src_path)

    def on_modified(self, event):
        self._check(event.src_path)

    def on_moved(self, event):
        self._check(event.dest_path)


if __name__ == "__main__":
    if "--install" in sys.argv:
        install_autostart()
        sys.exit(0)

    logging.info(f"[START] Surveillance de '{WATCH_FOLDER}' — {len(BANNED_WORDS)} signatures chargées")
    print(f"[*] FileGuard Watcher actif sur : {WATCH_FOLDER}")

    observer = Observer()
    observer.schedule(BanHandler(), WATCH_FOLDER, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("[STOP] Watcher arrêté manuellement")
    observer.join()