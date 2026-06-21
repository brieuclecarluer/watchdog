# 🔄 Auto-Build Guide

## Démarrage rapide

Pour activer la compilation automatique à chaque modification:

```powershell
python auto_build.py
```

## Ce que ça fait

✅ **Surveille** tous les fichiers `.py` du dossier `code/`
✅ **Recompile** automatiquement les 4 exécutables dès qu'une modification est détectée
✅ **Affiche** l'état de chaque build en temps réel
✅ **Évite les builds multiples** (délai de 2 secondes entre les builds)

## Arrêter

Appuyez sur **Ctrl+C** dans le terminal

## Exemple de sortie

```
🚀 Auto-build activé
📁 Surveillance des modifications: code/*.py
📋 Specs à builder: file_watcher.spec, FileGuard.spec, guardian.spec, restorer.spec
============================================================
Appuyez sur Ctrl+C pour arrêter

[14:23:45] 🔄 Changement détecté: guardian.py
------------------------------------------------------------

📦 Building: file_watcher.spec
✅ file_watcher.spec built successfully

📦 Building: FileGuard.spec
✅ FileGuard.spec built successfully

📦 Building: guardian.spec
✅ guardian.spec built successfully

📦 Building: restorer.spec
✅ restorer.spec built successfully
```

## Notes

- Les builds s'exécutent **séquentiellement** (~2-3 secondes chaque)
- Tous les 4 builds se lancent à chaque modification détectée
- Les fichiers `.spec` doivent exister dans le répertoire racine
