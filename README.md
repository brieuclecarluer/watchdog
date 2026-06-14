# Watchdog — Moniteur de Système de Fichiers Léger

> **Projet Portfolio — Cybersécurité / Blue Team**  
> Python · Windows 10/11 · watchdog · psutil · PyInstaller

---

## Vue d'ensemble

Watchdog est un moniteur de système de fichiers en temps réel écrit en Python. Il combine des signatures explicites (noms malveillants connus) et un moteur de scoring heuristique local pour classer et mettre en quarantaine les fichiers suspects, assure l'intégrité des documents protégés, et garantit sa propre persistance via un processus watchdog.

Conçu comme un exercice pratique sur les mécanismes de sécurité Windows : persistance par le registre, événements du système de fichiers via les API natives du système d'exploitation, et surveillance des processus.

---

## Architecture

Trois composants indépendants fonctionnant en parallèle :

| Composant | Rôle |
|---|---|
| `file_watcher.py` | Détection des menaces en temps réel, scoring et quarantaine |
| `restorer.py` | Application de l'intégrité des fichiers + extinction du PC en cas de falsification |
| `guardian.py` | Processus watchdog — relance les deux composants ci-dessus s'ils sont tués |
| `threat_engine.py` | Scoring heuristique local des risques + métadonnées des événements de quarantaine |

---

## Composants

### file_watcher.py — Scanner de Menaces

Surveille récursivement un dossier cible via `watchdog` (encapsule `ReadDirectoryChangesW` sur Windows). À chaque création, modification ou renommage de fichier/dossier :
- le nom du fichier est testé contre une regex compilée de 60+ noms de malwares connus, familles de ransomwares, outils offensifs et mots-clés suspects génériques
- un moteur heuristique local calcule un score de risque (extension, entropie, anomalies dans le nom de fichier, signaux de scripts/exécutables suspects)
- les fichiers suspects/malveillants sont déplacés en quarantaine avec des métadonnées JSONL, plutôt que supprimés immédiatement

**Choix de conception clés :**
- Regex insensible à la casse compilée une seule fois au démarrage — O(1) par vérification
- Couvre `on_created`, `on_modified` ET `on_moved` — détecte l'évasion par renommage
- Débounce des événements pour réduire les tempêtes de traitement en double
- Stratégie quarantaine-en-premier avec suppression en dernier recours si le déplacement échoue
- Démarrage automatique via le registre avec le flag `--install`
- Log rotatif (5 Mo max, 3 sauvegardes)

### threat_engine.py — Moteur Heuristique Local

Calcule un score léger sur 100 à partir de plusieurs signaux faibles, puis le mappe vers :
- `clean` (sain)
- `suspicious` (suspect)
- `malicious` (malveillant)

Il ne s'agit pas d'inférence par modèle ML, mais d'une stratégie de scoring local pratique de style « IA » utile pour des PC publics contraints ou hors ligne.

Il gère également le stockage en quarantaine et écrit un événement JSON par ligne dans :
- `%USERPROFILE%\FileGuard\quarantine\events.jsonl`

---

### restorer.py — Moniteur d'Intégrité des Fichiers

Surveille un ensemble de fichiers protégés et réagit aux événements de suppression ou de déplacement. Si un fichier protégé est supprimé, le système déclenche un arrêt Windows (délai de grâce de 5s) et recrée immédiatement le fichier avec son contenu d'origine.

**Choix de conception clés :**
- Basé sur un dictionnaire : `chemin → contenu`, facilement extensible à plusieurs fichiers
- `ensure_all()` au démarrage : recrée les fichiers manquants avant le lancement de l'observateur
- Couvre `on_deleted` ET `on_moved` — renommer le fichier déclenche aussi l'arrêt
- `shutdown /s /t 5` laisse un avertissement visible à l'utilisateur avant l'extinction

---

### guardian.py — Processus Watchdog

Interroge toutes les 5 secondes pour vérifier que `file_watcher.py` et `restorer.py` sont en cours d'exécution. Si l'un d'eux est absent (tué via le Gestionnaire des tâches ou crash), guardian le relance silencieusement.

**Choix de conception clés :**
- Utilise `psutil.process_iter` pour inspecter la ligne de commande de tous les processus en cours
- Comparaison `os.path.normcase` — insensible à la casse, gère les variantes de chemin
- Support natif des `.exe` — même code avant et après compilation PyInstaller
- Flag `DETACHED_PROCESS` — les processus relancés survivent à la mort de guardian

---

## Installation

### 1. Prérequis

Installer les dépendances Python :

```powershell
pip install -r requirements.txt
```

Ou manuellement :

```powershell
pip install watchdog>=4.0.0 psutil>=5.9.0 pyinstaller
```

### 2. Configuration

Modifier les constantes au début de chaque fichier :

```
file_watcher.py  →  WATCH_FOLDER, LOG_FILE
restorer.py      →  dictionnaire PROTECTED_FILES (chemin → contenu), LOG_FILE
guardian.py      →  liste GUARDED_SCRIPTS
```

### 3. Lancer en mode développement

```powershell
# Terminal 1
python code/file_watcher.py

# Terminal 2
python code/restorer.py

# Terminal 3
python code/guardian.py
```

### 4. Enregistrer au démarrage (optionnel)

```powershell
python code/file_watcher.py --install
python code/restorer.py     --install
python code/guardian.py     --install
```

Écrit dans `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` — aucun accès administrateur requis.

Vérifier :
```powershell
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
```

### 5. Masquer les fichiers (optionnel)

```powershell
attrib +h +s C:\Chemin\watchdog\code\*.py
attrib +h +s C:\Chemin\watchdog\code
```

### 6. Compiler en .exe (optionnel)

```powershell
cd C:\Chemin\watchdog\build
pyinstaller --onefile --noconsole --distpath .\dist ..\code\file_watcher.py
pyinstaller --onefile --noconsole --distpath .\dist ..\code\restorer.py
pyinstaller --onefile --noconsole --distpath .\dist ..\code\guardian.py
```

Mettre à jour `GUARDED_SCRIPTS` dans `guardian.py` pour pointer vers les chemins `.exe` avant de compiler.

### 7. Créer un raccourci sur le bureau (optionnel)

#### Option A : Via PowerShell

```powershell
$TargetPath = "C:\Chemin\watchdog\build\dist\guardian.exe"
$ShortcutPath = "$env:USERPROFILE\Desktop\Watchdog.lnk"
$WshShell = New-Object -ComObject WScript.Shell

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WindowStyle = 7  # Mode masqué
$Shortcut.Save()

Write-Host "Raccourci créé : $ShortcutPath"
```

#### Option B : Manuellement

1. Clic droit sur le fichier `.exe` (ou `python file_watcher.py`)
2. Envoyer vers → Bureau (créer un raccourci)
3. Renommer le raccourci en « Watchdog »

---

## Fonctionnement Interne

### Watchdog & API Windows

`watchdog` encapsule `ReadDirectoryChangesW`, l'API Windows native pour la notification asynchrone des changements de répertoire. C'est le même mécanisme qu'utilise Windows Defender — purement événementiel, sans polling.

### Moteur Regex

Tous les mots bannis sont compilés en un seul motif d'alternance au démarrage :

```python
re.compile(r"(mot1|mot2|...)", re.IGNORECASE)
```

Plus efficace que de parcourir une liste — le moteur regex utilise un NFA/DFA et fait correspondre tous les motifs en un seul passage sur la chaîne du nom de fichier.

### Persistance par le Registre

Les clés `HKCU\...\Run` sont exécutées par Windows Explorer à la connexion pour l'utilisateur courant, sans nécessiter de droits administrateur. Identique au fonctionnement de la plupart des applications légitimes en arrière-plan.

### Processus Watchdog

`guardian.py` inspecte la `cmdline` de chaque processus en cours via `psutil`. Si un processus a le chemin du script comme argument, il est considéré comme actif. Tuer `pythonw.exe` dans le Gestionnaire des tâches le retire de la liste des processus — guardian le détecte en 5 secondes et le relance.

---

## Couverture des Signatures de Menaces

| Catégorie | Exemples |
|---|---|
| Ransomwares | WannaCry, Petya, NotPetya, Locky, REvil, LockBit, BlackCat, Conti, Clop, Hive, Ryuk, DarkSide, Maze, GandCrab, Cerber, CryptoLocker, Avaddon, Egregor... |
| RATs / Stealers | njRAT, DarkComet, AsyncRAT, Quasar, Remcos, NanoCore, Emotet, TrickBot, Dridex, RedLine, Vidar, Raccoon, AZORult, FormBook, Agent Tesla, Warzone... |
| Frameworks C2 | Metasploit, Cobalt Strike, Empire, PowerSploit, Mimikatz, Havoc, Sliver, Brute Ratel, Pupy, Meterpreter, Shellter... |
| Web Shells | c99shell, r57shell, b374k, Weevely, AntSword, Chopper |
| Mots-clés génériques | malware, ransomware, exploit, payload, shellcode, backdoor, trojan, rootkit, keylogger, dropper, crypter, worm... |
| Outils offensifs | sqlmap, Mimikatz, Aircrack, Hashcat, john_the_ripper, masscan, hydra_brute... |

---

## Limitations & Travaux Futurs

### Limitations actuelles

- **Pas un antivirus noyau** — espace utilisateur uniquement, pas de pilote noyau ni d'analyse de la mémoire des processus
- **Scoring heuristique local** — meilleur qu'une simple vérification par nom, mais pas équivalent aux moteurs EDR/AV d'entreprise
- **Pas de surveillance réseau** — système de fichiers local uniquement
- **Espace utilisateur** — les processus de niveau SYSTEM peuvent contourner la protection
- **Mode sans échec** — les clés `HKCU\Run` ne s'exécutent pas en mode sans échec Windows
- **Pas de flux de réputation cloud par défaut** — pas d'intégration VirusTotal/SIEM encore
- Les mots-clés génériques (`trojan`, `virus`) peuvent produire des faux positifs sur des fichiers de recherche en sécurité

### Extensions possibles

- **Détection par hash** — calculer le SHA256 à la création du fichier, interroger l'API VirusTotal
- **Analyse du contenu** — détecter la chaîne de test EICAR, les en-têtes PE embarqués, les patterns de shellcode en base64
- **Mode quarantaine** — déplacer vers un dossier chiffré plutôt que de supprimer
- **Règles YARA** — intégrer `yara-python` pour l'analyse de contenu basée sur des motifs
- **Intégration SIEM** — transmettre les événements de log vers Elasticsearch / Splunk
- **Service Windows** — utiliser `pywin32` pour s'exécuter en tant que SYSTEM, sans nécessiter de session utilisateur

---

## Stack Technique

| Bibliothèque | Rôle |
|---|---|
| `watchdog` | Surveillance des événements du système de fichiers (encapsule `ReadDirectoryChangesW`) |
| `psutil` | Inspection des processus multiplateforme |
| `winreg` | Lecture/écriture du Registre Windows (stdlib) |
| `re` | Regex compilée pour la correspondance multi-motifs (stdlib) |
| `shutil` | Suppression récursive de répertoires (stdlib) |
| `logging` | Log d'événements horodaté rotatif (stdlib) |
| `subprocess` | Exécution de la commande d'arrêt Windows (stdlib) |
| `PyInstaller` | Empaquetage des scripts en binaires `.exe` autonomes |
