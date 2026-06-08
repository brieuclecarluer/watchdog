# 🛡️ FileGuard — Lightweight File System Monitor

> **Portfolio Project — Cybersecurity / Blue Team**  
> Python · Windows 10/11 · watchdog · psutil · PyInstaller

---

## Overview

FileGuard is a real-time file system monitor built in Python. It now combines explicit signatures (known bad names) and a local heuristic scoring engine ("AI-style" risk scoring) to classify and quarantine suspicious files, enforces integrity on protected documents, and ensures its own persistence through a process watchdog.

Built as a hands-on exercise in Windows security mechanisms: registry persistence, file system events via native OS APIs, and process monitoring.

---

## Architecture

Three independent components running in parallel:

| Component | Role |
|---|---|
| `file_watcher.py` | Real-time threat detection, scoring, and quarantine |
| `restorer.py` | File integrity enforcement + PC shutdown on tampering |
| `guardian.py` | Process watchdog — relaunches the two above if killed |
| `threat_engine.py` | Local heuristic risk scoring + quarantine event metadata |

---

## Components

### file_watcher.py — Threat Scanner

Monitors a target folder recursively using `watchdog` (wraps `ReadDirectoryChangesW` on Windows). On every file/folder creation, modification, or rename:
- the filename is tested against a compiled regex of 60+ known malware names, ransomware families, offensive tools, and generic suspicious keywords
- a local heuristic engine computes a risk score (extension, entropy, filename anomalies, tiny script/executable signals)
- suspicious/malicious files are moved to quarantine with JSONL metadata instead of immediate hard delete

**Key design choices:**
- Case-insensitive regex compiled once at startup — O(1) per check
- Covers `on_created`, `on_modified` AND `on_moved` — catches evasion via rename
- Event debounce to reduce duplicate processing storms
- Quarantine-first strategy with delete fallback if move fails
- Registry autostart via `--install` flag
- Rotating log (5 MB max, 3 backups)

### threat_engine.py — Local Heuristic Engine

Computes a lightweight score out of 100 from multiple weak signals, then maps it to:
- `clean`
- `suspicious`
- `malicious`

This is not ML model inference, but a practical local "AI-style" scoring strategy useful for constrained/offline public PCs.

It also handles quarantine storage and writes one JSON event per line in:
- `%USERPROFILE%\FileGuard\quarantine\events.jsonl`

---

### restorer.py — File Integrity Monitor

Watches a set of protected files and reacts to deletion or move events. If a protected file is removed, the system triggers a Windows shutdown (5s grace period) and immediately recreates the file with its original content.

**Key design choices:**
- Dictionary-based: `path → content`, easily extensible to multiple files
- `ensure_all()` at startup: recreates missing files before the observer starts
- Covers `on_deleted` AND `on_moved` — renaming the file also triggers shutdown
- `shutdown /s /t 5` gives the user a visible warning before poweroff

---

### guardian.py — Process Watchdog

Polls every 5 seconds to verify that `file_watcher.py` and `restorer.py` are running. If either is missing (killed via Task Manager or crash), guardian relaunches it silently.

**Key design choices:**
- Uses `psutil.process_iter` to inspect cmdline of all running processes
- `os.path.normcase` comparison — case-insensitive, handles path variants
- Native `.exe` support — same code before and after PyInstaller compilation
- `DETACHED_PROCESS` flag — relaunched processes survive guardian being killed

---

## Installation

### 1. Prerequisites

```
pip install watchdog psutil pyinstaller
```

### 2. Configuration

Edit the constants at the top of each file:

```
file_watcher.py  →  WATCH_FOLDER, LOG_FILE
restorer.py      →  PROTECTED_FILES dict (path → content), LOG_FILE
guardian.py      →  GUARDED_SCRIPTS list
```

### 3. Register autostart

```powershell
python file_watcher.py --install
python restorer.py     --install
python guardian.py     --install
```

Writes to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` — no admin required.

Verify:
```powershell
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
```

### 4. Hide the files (optional)

```powershell
attrib +h +s C:\Tools\file_watcher.py
attrib +h +s C:\Tools\restorer.py
attrib +h +s C:\Tools\guardian.py
attrib +h +s C:\Tools
```

### 5. Build standalone .exe (optional)

```powershell
cd C:\Users\<user>\Desktop
pyinstaller --onefile --noconsole --distpath .\dist C:\Tools\file_watcher.py
pyinstaller --onefile --noconsole --distpath .\dist C:\Tools\restorer.py
pyinstaller --onefile --noconsole --distpath .\dist C:\Tools\guardian.py
```

> Update `GUARDED_SCRIPTS` in `guardian.py` to point to the `.exe` paths before building.

---

## How It Works — Internals

### Watchdog & Windows API

`watchdog` wraps `ReadDirectoryChangesW`, the native Windows API for asynchronous directory change notification. This is the same mechanism used by Windows Defender — purely event-driven, no polling.

### Regex engine

All banned words are compiled into a single alternation pattern at startup:

```python
re.compile(r"(word1|word2|...)", re.IGNORECASE)
```

More efficient than looping through a list — the regex engine uses an NFA/DFA and matches all patterns in a single pass over the filename string.

### Registry persistence

`HKCU\...\Run` keys are executed by Windows Explorer at login for the current user, without requiring admin privileges. Identical to how most legitimate background apps persist.

### Process watchdog

`guardian.py` inspects the `cmdline` of every running process via `psutil`. If a process has the script path as an argument, it is considered running. Killing `pythonw.exe` in Task Manager removes it from the process list — guardian detects this within 5 seconds and relaunches it.

---

## Threat Signature Coverage

| Category | Examples |
|---|---|
| Ransomware | WannaCry, Petya, NotPetya, Locky, REvil, LockBit, BlackCat, Conti, Clop, Hive, Ryuk, DarkSide, Maze, GandCrab, Cerber, CryptoLocker, Avaddon, Egregor... |
| RATs / Stealers | njRAT, DarkComet, AsyncRAT, Quasar, Remcos, NanoCore, Emotet, TrickBot, Dridex, RedLine, Vidar, Raccoon, AZORult, FormBook, Agent Tesla, Warzone... |
| C2 Frameworks | Metasploit, Cobalt Strike, Empire, PowerSploit, Mimikatz, Havoc, Sliver, Brute Ratel, Pupy, Meterpreter, Shellter... |
| Web Shells | c99shell, r57shell, b374k, Weevely, AntSword, Chopper |
| Generic keywords | malware, ransomware, exploit, payload, shellcode, backdoor, trojan, rootkit, keylogger, dropper, crypter, worm... |
| Offensive tools | sqlmap, Mimikatz, Aircrack, Hashcat, john_the_ripper, masscan, hydra_brute... |

---

## Limitations & Future Work

### Current limitations

- **Not a kernel AV** — user-space only, no kernel driver and no process memory scan
- **Heuristic local scoring** — better than name-only, but still not equivalent to enterprise EDR/AV engines
- **No network monitoring** — local filesystem only
- **User-space** — SYSTEM-level processes can bypass
- **Safe mode** — `HKCU\Run` keys don't execute in Windows Safe Mode
- **No cloud reputation feed by default** — no VirusTotal/SIEM enrichment yet
- Generic keywords (`trojan`, `virus`) may produce false positives on security research files

### Possible extensions

- **Hash-based detection** — compute SHA256 on file creation, query VirusTotal API
- **Content scanning** — detect EICAR test string, embedded PE headers, base64 shellcode patterns
- **Quarantine mode** — move to an encrypted folder instead of deleting
- **YARA rules** — integrate `yara-python` for pattern-based content scanning
- **SIEM integration** — forward log events to Elasticsearch / Splunk
- **Windows Service** — use `pywin32` to run as SYSTEM, surviving without a user session

---

## Technical Stack

| Library | Role |
|---|---|
| `watchdog` | File system event monitoring (wraps `ReadDirectoryChangesW`) |
| `psutil` | Cross-platform process inspection |
| `winreg` | Windows Registry read/write (stdlib) |
| `re` | Compiled regex for multi-pattern matching (stdlib) |
| `shutil` | Recursive directory deletion (stdlib) |
| `logging` | Rotating timestamped event log (stdlib) |
| `subprocess` | Windows shutdown command execution (stdlib) |
| `PyInstaller` | Packages scripts into standalone `.exe` binaries |
