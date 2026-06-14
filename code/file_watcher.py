import os
import re
import time
import shutil
import logging
import logging.handlers
import sys
import winreg
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threat_engine import LocalThreatEngine, QuarantineManager

# CONFIG
WATCH_FOLDER = os.path.expanduser(r"~")  # home user
LOG_FILE = os.path.join(os.path.expanduser("~"), "fileguard.log")
SCRIPT_PATH = os.path.abspath(__file__)
MAX_LOG_MB = 5
QUARANTINE_DIR = os.path.join(os.path.expanduser("~"), "FileGuard", "quarantine")
EVENT_DEBOUNCE_SECONDS = 2.0

BANNED_WORDS = [
    # Ransomware
    "wannacry", "wannacrypt", "petya", "notpetya", "locky", "ryuk", "revil",
    "darkside", "conti", "lockbit", "blackcat", "alphv", "maze", "sodinokibi",
    "gandcrab", "cerber", "cryptolocker", "cryptowall", "badrabbit", "samsa",
    "clop", "hive", "ragnarok", "netwalker", "egregor", "avaddon",
    # RATs & Stealers
    "njrat", "darkcomet", "asyncrat", "quasar", "remcos", "nanocore",
    "xtremerat", "cybergate", "pandabanker", "emotet", "trickbot", "dridex",
    "agent tesla", "agent_tesla", "formbook", "azorult", "hawkeye", "loki",
    "raccoon", "redline", "vidar", "arkei", "warzone",
    # C2 & Offensive tools
    "metasploit", "msfvenom", "msfconsole", "cobalt strike", "cobaltstrike",
    "empire", "powersploit", "mimikatz", "meterpreter", "shellter",
    "veil", "unicorn", "pupy", "havoc", "brute ratel", "bruteratel", "sliver",
    # Spyware & Stalkerware
    "stalkerware", "pegasus", "finspy", "darkspy",
    # Bootkits & Rootkits
    "bootkit", "necurs", "rustock", "tdss", "zeroaccess",
    # Botnets & Worms
    "mirai", "conficker", "stuxnet", "flame", "regin", "sality",
    "zeus", "gameover", "blackenergy", "industroyer", "triton",
    # Recon & cracking
    "nmap_scan", "masscan", "zmap", "sqlmap", "hydra_brute",
    "aircrack", "hashcat", "johntheripper", "john_the_ripper",
    # Web shells & Backdoors
    "netcat_backdoor", "weevely", "webshell", "c99shell", "r57shell",
    "b374k", "antsword", "chopper",
    # Generic threats
    "malware", "ransomware", "exploit", "payload", "shellcode", "backdoor",
    "rootkit", "keylogger", "spyware", "trojan", "dropper",
    "crypter", "bypass_av", "antivirus_bypass",
]

# Une seule regex = pas de boucle = plus rapide
BANNED_PATTERN = re.compile(
    r"(" + "|".join(re.escape(w) for w in BANNED_WORDS) + r")",
    re.IGNORECASE
)

_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=MAX_LOG_MB * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().addHandler(_handler)
logging.getLogger().setLevel(logging.INFO)


def install_autostart():
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable  # fallback
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


ENGINE = LocalThreatEngine()
QUARANTINE = QuarantineManager(QUARANTINE_DIR)


class BanHandler(FileSystemEventHandler):
    def __init__(self) -> None:
        super().__init__()
        self._last_seen: dict[str, float] = {}

    def _is_debounced(self, path: str) -> bool:
        now = time.time()
        last = self._last_seen.get(path, 0.0)
        self._last_seen[path] = now
        return (now - last) < EVENT_DEBOUNCE_SECONDS

    def _check(self, path: str) -> None:
        if self._is_debounced(path):
            return

        banned, word = is_banned(path)
        if banned:
            logging.info(f"[DETECTED] '{os.path.basename(path)}' — mot banni : '{word}'")
            scan = ENGINE.evaluate(path)
            ok, destination = QUARANTINE.quarantine(path, scan)
            if ok:
                logging.warning(
                    f"[QUARANTINE] {path} -> {destination} | score={scan.score} | reasons={','.join(scan.reasons)}"
                )
            else:
                logging.warning(f"[QUARANTINE_FAILED] {path} | fallback delete | error={destination}")
                delete_target(path)
            return

        # "AI-style" local risk scoring even when no explicit banned keyword matches.
        scan = ENGINE.evaluate(path)
        if scan.verdict in {"suspicious", "malicious"}:
            ok, destination = QUARANTINE.quarantine(path, scan)
            if ok:
                logging.warning(
                    f"[QUARANTINE_HEURISTIC] {path} -> {destination} | verdict={scan.verdict} | score={scan.score}"
                )
            else:
                logging.warning(f"[QUARANTINE_HEURISTIC_FAILED] {path} | error={destination}")

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

    logging.info(
        f"[START] Surveillance de '{WATCH_FOLDER}' — {len(BANNED_WORDS)} signatures chargées | quarantine={QUARANTINE_DIR}"
    )
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