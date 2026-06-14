# Watchdog — Moniteur de système de fichiers léger

> **Projet portfolio — Cybersécurité / Blue Team**  
> Python · Windows 10/11 · watchdog · psutil · PyInstaller

---

## Présentation

Watchdog surveille un dossier en temps réel et détecte les fichiers suspects à partir de signatures connues et d'un scoring heuristique local. Les fichiers identifiés comme malveillants sont mis en quarantaine automatiquement. Le projet couvre aussi l'intégrité de fichiers protégés et sa propre persistance via un processus gardien.

C'est un projet pratique pour explorer les mécanismes de sécurité Windows : persistance par le registre, surveillance du système de fichiers via l'API native, et monitoring de processus.

---

## Architecture

Trois composants indépendants tournent en parallèle :

| Composant | Rôle |
|---|---|
| `file_watcher.py` | Détection des menaces, scoring et mise en quarantaine |
| `restorer.py` | Intégrité des fichiers protégés + extinction du PC en cas de suppression |
| `guardian.py` | Relance les deux composants ci-dessus s'ils sont tués |
| `threat_engine.py` | Calcul du score de risque + écriture des métadonnées de quarantaine |

---

## Composants

### file_watcher.py — Scanner de menaces

Surveille récursivement un dossier cible via `watchdog` (qui encapsule `ReadDirectoryChangesW` sur Windows). À chaque création, modification ou renommage :

- le nom du fichier est comparé à une regex compilée de 60+ signatures (noms de malwares, familles de ransomwares, outils offensifs, mots-clés génériques)
- un score de risque est calculé localement (extension, entropie, anomalies dans le nom, présence de scripts ou d'exécutables suspects)
- les fichiers détectés sont déplacés en quarantaine avec métadonnées JSONL — la suppression directe n'est qu'un recours si le déplacement échoue

Points notables :
- regex insensible à la casse, compilée une seule fois au démarrage — O(1) par vérification
- couvre `on_created`, `on_modified` et `on_moved` pour attraper les tentatives d'évasion par renommage
- débounce des événements pour éviter les doublons
- démarrage automatique via le registre avec `--install`
- log rotatif (5 Mo max, 3 sauvegardes)

### threat_engine.py — Moteur de scoring

Agrège plusieurs signaux faibles en un score sur 100, puis le classe en :

- `clean`
- `suspicious`
- `malicious`

Pas de modèle ML — c'est du scoring heuristique pur, conçu pour fonctionner hors ligne sur des machines contraintes. Les événements de quarantaine sont écrits ligne par ligne dans :

```
%USERPROFILE%\FileGuard\quarantine\events.jsonl
```

### restorer.py — Intégrité des fichiers

Surveille un ensemble de fichiers protégés. Si l'un d'eux est supprimé ou déplacé, le système recrée immédiatement le fichier avec son contenu d'origine et déclenche un arrêt Windows avec 5 secondes de délai.

Points notables :
- structure `chemin → contenu` sous forme de dictionnaire, simple à étendre
- `ensure_all()` au démarrage recrée les fichiers manquants avant que l'observateur ne commence
- couvre `on_deleted` et `on_moved` — renommer le fichier déclenche aussi l'arrêt

### guardian.py — Processus gardien

Vérifie toutes les 5 secondes que `file_watcher.py` et `restorer.py` tournent. Si l'un est absent (tué depuis le gestionnaire des tâches ou crash), il est relancé silencieusement.

Points notables :
- inspecte la ligne de commande de chaque processus via `psutil.process_iter`
- comparaison `os.path.normcase` — insensible à la casse, robuste aux variantes de chemin
- fonctionne aussi bien avec les `.py` qu'avec les `.exe` compilés
- flag `DETACHED_PROCESS` — les processus relancés survivent si guardian lui-même est tué

---

## Installation

### 1. Prérequis

```powershell
pip install -r requirements.txt
```

Ou manuellement :

```powershell
pip install watchdog>=4.0.0 psutil>=5.9.0 pyinstaller
```

### 2. Configuration

Modifier les constantes en tête de chaque fichier :

```
file_watcher.py  →  WATCH_FOLDER, LOG_FILE
restorer.py      →  PROTECTED_FILES (chemin → contenu), LOG_FILE
guardian.py      →  GUARDED_SCRIPTS
```

### 3. Lancement en mode développement

```powershell
# Terminal 1
python code/file_watcher.py

# Terminal 2
python code/restorer.py

# Terminal 3
python code/guardian.py
```

### 4. Démarrage automatique (optionnel)

```powershell
python code/file_watcher.py --install
python code/restorer.py     --install
python code/guardian.py     --install
```

Écrit dans `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` — aucun droit administrateur requis.

Pour vérifier :
```powershell
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
```

### 5. Masquer les fichiers (optionnel)

```powershell
attrib +h +s C:\Chemin\watchdog\code\*.py
attrib +h +s C:\Chemin\watchdog\code
```

### 6. Compilation en .exe (optionnel)

```powershell
cd C:\Chemin\watchdog\build
pyinstaller --onefile --noconsole --distpath .\dist ..\code\file_watcher.py
pyinstaller --onefile --noconsole --distpath .\dist ..\code\restorer.py
pyinstaller --onefile --noconsole --distpath .\dist ..\code\guardian.py
```

Mettre à jour `GUARDED_SCRIPTS` dans `guardian.py` pour pointer vers les `.exe` avant de compiler.

### 7. Raccourci bureau (optionnel)

**Via PowerShell :**

```powershell
$TargetPath = "C:\Chemin\watchdog\build\dist\guardian.exe"
$ShortcutPath = "$env:USERPROFILE\Desktop\Watchdog.lnk"
$WshShell = New-Object -ComObject WScript.Shell

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WindowStyle = 7
$Shortcut.Save()

Write-Host "Raccourci créé : $ShortcutPath"
```

**Manuellement :**

1. Clic droit sur le `.exe`
2. Envoyer vers → Bureau (créer un raccourci)
3. Renommer en « Watchdog »

---

## Fonctionnement

### Watchdog et l'API Windows

`watchdog` encapsule `ReadDirectoryChangesW`, l'API Windows de notification asynchrone des changements de répertoire — le même mécanisme que Windows Defender. Aucun polling, tout est événementiel.

### Regex

Les signatures sont compilées en une seule alternance au démarrage :

```python
re.compile(r"(mot1|mot2|...)", re.IGNORECASE)
```

Le moteur regex (NFA/DFA) parcourt la chaîne une seule fois pour toutes les règles, ce qui est plus efficace qu'une boucle sur une liste.

### Persistance par le registre

Les clés `HKCU\...\Run` sont exécutées par Explorer à la connexion, sans droits administrateur — c'est le même mécanisme que la majorité des applications de démarrage.

### Processus gardien

`guardian.py` cherche dans les arguments de chaque processus le chemin du script surveillé. Si `pythonw.exe` est tué dans le gestionnaire des tâches, guardian le détecte en moins de 5 secondes et le relance.

---

## Signatures couvertes

| Catégorie | Exemples |
|---|---|
| Ransomwares | WannaCry, Petya, NotPetya, Locky, REvil, LockBit, BlackCat, Conti, Clop, Hive, Ryuk, DarkSide, Maze, GandCrab, Cerber, CryptoLocker, Avaddon, Egregor... |
| RATs / Stealers | njRAT, DarkComet, AsyncRAT, Quasar, Remcos, NanoCore, Emotet, TrickBot, Dridex, RedLine, Vidar, Raccoon, AZORult, FormBook, Agent Tesla, Warzone... |
| Frameworks C2 | Metasploit, Cobalt Strike, Empire, PowerSploit, Mimikatz, Havoc, Sliver, Brute Ratel, Pupy, Meterpreter, Shellter... |
| Web shells | c99shell, r57shell, b374k, Weevely, AntSword, Chopper |
| Mots-clés génériques | malware, ransomware, exploit, payload, shellcode, backdoor, trojan, rootkit, keylogger, dropper, crypter, worm... |
| Outils offensifs | sqlmap, Mimikatz, Aircrack, Hashcat, john_the_ripper, masscan, hydra_brute... |

---

## Limites et pistes d'évolution

### Limites actuelles

- **Espace utilisateur uniquement** — pas de pilote noyau, pas d'analyse mémoire des processus
- **Scoring heuristique** — plus efficace qu'une simple liste noire, mais loin d'un EDR/AV commercial
- **Pas de surveillance réseau** — uniquement le système de fichiers local
- **Contournable par SYSTEM** — un processus avec des droits suffisants peut ignorer le moniteur
- **Mode sans échec** — les clés `HKCU\Run` ne s'exécutent pas en mode sans échec
- **Pas de réputation cloud** — aucune intégration VirusTotal ou SIEM par défaut
- Risque de faux positifs sur des fichiers de recherche en sécurité (mots-clés comme `trojan`, `virus`)

### Pistes d'évolution

- **Détection par hash** — SHA256 à la création, requête vers l'API VirusTotal
- **Analyse du contenu** — chaîne EICAR, en-têtes PE embarqués, shellcode en base64
- **Quarantaine chiffrée** — déplacement dans un conteneur chiffré plutôt que suppression
- **Règles YARA** — intégration de `yara-python` pour la détection par motifs
- **Intégration SIEM** — export des logs vers Elasticsearch ou Splunk
- **Service Windows** — exécution en tant que SYSTEM via `pywin32`, sans session utilisateur active

---

## Dépendances

| Bibliothèque | Rôle |
|---|---|
| `watchdog` | Surveillance du système de fichiers (encapsule `ReadDirectoryChangesW`) |
| `psutil` | Inspection des processus |
| `winreg` | Lecture/écriture du registre Windows (stdlib) |
| `re` | Regex compilée pour la détection multi-signatures (stdlib) |
| `shutil` | Suppression récursive de dossiers (stdlib) |
| `logging` | Log rotatif horodaté (stdlib) |
| `subprocess` | Commande d'arrêt Windows (stdlib) |
| `PyInstaller` | Compilation en binaires `.exe` autonomes |
