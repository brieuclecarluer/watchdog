#!/usr/bin/env python3
"""
Auto-build script: surveille les fichiers .py et relance PyInstaller automatiquement
"""

import time
import subprocess
import sys
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime

class BuildHandler(FileSystemEventHandler):
    def __init__(self, specs):
        self.specs = specs
        self.last_build = 0
        self.debounce_interval = 2  # Évite les builds multiples rapides
        
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if not event.src_path.endswith('.py'):
            return
        
        current_time = time.time()
        if current_time - self.last_build < self.debounce_interval:
            return
        
        self.last_build = current_time
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"\n[{timestamp}] 🔄 Changement détecté: {Path(event.src_path).name}")
        print("-" * 60)
        
        self.build_all()
    
    def build_all(self):
        """Relance tous les builds PyInstaller"""
        for spec_file in self.specs:
            self.build_spec(spec_file)
    
    def build_spec(self, spec_file):
        """Relance un build PyInstaller spécifique"""
        spec_path = Path(spec_file)
        print(f"\n Building: {spec_path.name}")
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "PyInstaller", str(spec_path)],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                print(f"✅ {spec_path.name} built successfully")
            else:
                print(f"❌ {spec_path.name} build failed")
                if result.stderr:
                    print(f"Error: {result.stderr[:500]}")
        except subprocess.TimeoutExpired:
            print(f"  Build timeout for {spec_path.name}")
        except Exception as e:
            print(f"❌ Error building {spec_path.name}: {e}")

def main():
    # Définir les fichiers .spec à surveiller
    specs = [
        "file_watcher.spec",
        "FileGuard.spec", 
        "guardian.spec",
        "restorer.spec"
    ]
    
    # Vérifier que les fichiers .spec existent
    for spec in specs:
        if not Path(spec).exists():
            print(f"⚠️  Fichier non trouvé: {spec}")
            return 1
    
    print(" Auto-build activé")
    print(f" Surveillance des modifications: code/*.py")
    print(f" Specs à builder: {', '.join(specs)}")
    print("=" * 60)
    print("Appuyez sur Ctrl+C pour arrêter\n")
    
    # Configurer le watcher
    handler = BuildHandler(specs)
    observer = Observer()
    observer.schedule(handler, path="code", recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Arrêt de la surveillance...")
        observer.stop()
    
    observer.join()
    print("✨ Auto-build arrêté")
    return 0

if __name__ == "__main__":
    sys.exit(main())
