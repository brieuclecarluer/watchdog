import sys
import os
import json
import time
import threading
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QStackedWidget, QFileDialog,
    QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

# ── Palette ───────────────────────────────────────────────────────────────────
BG_MAIN  = "#0D1117"
BG_SIDE  = "#10161E"
BG_CARD  = "#161B22"
BG_HOVER = "#1C2333"
BORDER   = "#30363D"
TEXT_PRI = "#E6EDF3"
TEXT_SEC = "#8B949E"
ACCENT   = "#238636"
ACCENT2  = "#1F6FEB"
WARN     = "#D29922"
DANGER   = "#DA3633"
CLEAN    = "#3FB950"


def stylesheet() -> str:
    return f"""
    QMainWindow, QWidget {{ background: {BG_MAIN}; color: {TEXT_PRI}; font-family: 'Segoe UI'; font-size: 13px; }}
    QFrame#sidebar {{ background: {BG_SIDE}; border-right: 1px solid {BORDER}; }}
    QFrame#card {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px; }}
    QPushButton#nav {{ background: transparent; color: {TEXT_SEC}; border: none; text-align: left;
        padding: 10px 16px; border-radius: 6px; font-size: 13px; }}
    QPushButton#nav:hover {{ background: {BG_HOVER}; color: {TEXT_PRI}; }}
    QPushButton#nav:checked {{ background: {BG_HOVER}; color: {TEXT_PRI}; border-left: 3px solid {ACCENT}; }}
    QPushButton#action {{ background: {ACCENT}; color: white; border: none; border-radius: 6px;
        padding: 8px 18px; font-weight: 600; }}
    QPushButton#action:hover {{ background: #2EA043; }}
    QPushButton#action_blue {{ background: {ACCENT2}; color: white; border: none; border-radius: 6px;
        padding: 8px 18px; font-weight: 600; }}
    QPushButton#action_blue:hover {{ background: #388BFD; }}
    QPushButton#danger {{ background: {DANGER}; color: white; border: none; border-radius: 6px;
        padding: 6px 14px; font-weight: 600; font-size: 12px; }}
    QPushButton#danger:hover {{ background: #F85149; }}
    QTableWidget {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px;
        gridline-color: {BORDER}; color: {TEXT_PRI}; }}
    QTableWidget::item {{ padding: 8px; border-bottom: 1px solid {BORDER}; }}
    QTableWidget::item:selected {{ background: {BG_HOVER}; color: {TEXT_PRI}; }}
    QHeaderView::section {{ background: {BG_SIDE}; color: {TEXT_SEC}; border: none;
        border-bottom: 1px solid {BORDER}; padding: 8px; font-size: 12px; font-weight: 600; }}
    QScrollBar:vertical {{ background: {BG_MAIN}; width: 6px; border-radius: 3px; }}
    QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
    QScrollBar:horizontal {{ height: 0px; }}
    QLabel#title {{ font-size: 20px; font-weight: 700; color: {TEXT_PRI}; }}
    QLabel#subtitle {{ font-size: 12px; color: {TEXT_SEC}; }}
    QLabel#stat_val {{ font-size: 28px; font-weight: 700; color: {TEXT_PRI}; }}
    QLabel#stat_lbl {{ font-size: 11px; color: {TEXT_SEC}; }}
    QLabel#status_on {{ color: {CLEAN}; font-size: 12px; font-weight: 600; }}
    QLabel#status_off {{ color: {DANGER}; font-size: 12px; font-weight: 600; }}
    QProgressBar {{ background: {BG_SIDE}; border: 1px solid {BORDER}; border-radius: 4px; height: 6px; text-align: center; }}
    QProgressBar::chunk {{ background: {ACCENT2}; border-radius: 4px; }}
    QFrame#divider {{ background: {BORDER}; max-height: 1px; }}
    """


class EventItem(QFrame):
    def __init__(self, path: str, verdict: str, ts: int, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedHeight(68)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        color = CLEAN if verdict == "clean" else (WARN if verdict == "suspicious" else DANGER)
        dot = QLabel("●")
        dot.setFixedWidth(14)
        dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        layout.addWidget(dot)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(os.path.basename(path))
        name_lbl.setStyleSheet(f"color: {TEXT_PRI}; font-weight: 600; font-size: 13px;")
        path_lbl = QLabel(path[:72] + "..." if len(path) > 72 else path)
        path_lbl.setStyleSheet(f"color: {TEXT_SEC}; font-size: 11px;")
        info.addWidget(name_lbl)
        info.addWidget(path_lbl)
        layout.addLayout(info)
        layout.addStretch()

        right = QVBoxLayout()
        right.setSpacing(4)
        right.setAlignment(Qt.AlignmentFlag.AlignRight)

        badge_colors = {
            "clean":      (f"background:#1A3A1F; color:{CLEAN};"),
            "suspicious": (f"background:#2D2008; color:{WARN};"),
            "malicious":  (f"background:#3D0E0E; color:{DANGER};"),
        }
        badge = QLabel(verdict.upper())
        badge.setStyleSheet(f"{badge_colors.get(verdict, '')} border-radius:10px; padding:2px 10px; font-size:11px; font-weight:600;")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        time_lbl = QLabel(datetime.fromtimestamp(ts).strftime("%H:%M:%S"))
        time_lbl.setStyleSheet(f"color: {TEXT_SEC}; font-size: 11px;")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        right.addWidget(badge)
        right.addWidget(time_lbl)
        layout.addLayout(right)


class StatCard(QFrame):
    def __init__(self, label: str, value: str, color: str = TEXT_PRI, icon: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(90)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)

        top = QHBoxLayout()
        lbl = QLabel(label.upper())
        lbl.setObjectName("stat_lbl")
        top.addWidget(lbl)
        top.addStretch()
        if icon:
            ico = QLabel(icon)
            ico.setStyleSheet(f"font-size: 18px; color: {color};")
            top.addWidget(ico)
        layout.addLayout(top)

        self.val_lbl = QLabel(value)
        self.val_lbl.setObjectName("stat_val")
        self.val_lbl.setStyleSheet(f"color: {color};")
        layout.addWidget(self.val_lbl)

    def update_value(self, value: str):
        self.val_lbl.setText(value)


class LogWatcher(QThread):
    new_event = pyqtSignal(dict)

    def __init__(self, jsonl_path: str):
        super().__init__()
        self.jsonl_path = jsonl_path
        self._running = True
        self._seen = 0

    def run(self):
        while self._running:
            if os.path.exists(self.jsonl_path):
                with open(self.jsonl_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if len(lines) > self._seen:
                    for line in lines[self._seen:]:
                        try:
                            self.new_event.emit(json.loads(line.strip()))
                        except Exception:
                            pass
                    self._seen = len(lines)
            time.sleep(1.5)

    def stop(self):
        self._running = False


class ScanWorker(QThread):
    progress = pyqtSignal(int, int)
    result   = pyqtSignal(dict)
    done     = pyqtSignal()

    def __init__(self, folder: str):
        super().__init__()
        self.folder = folder

    def run(self):
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from threat_engine import LocalThreatEngine
            engine = LocalThreatEngine()
        except ImportError:
            self.done.emit()
            return

        files = []
        for root, _, fnames in os.walk(self.folder):
            for fn in fnames:
                files.append(os.path.join(root, fn))

        for i, path in enumerate(files):
            self.progress.emit(i + 1, len(files))
            try:
                r = engine.evaluate(path)
                if r.verdict != "clean":
                    self.result.emit({
                        "src_path": r.path,
                        "verdict": r.verdict,
                        "score": r.score,
                        "reasons": r.reasons,
                        "sha256": r.sha256,
                        "timestamp": int(time.time()),
                    })
            except Exception:
                pass
        self.done.emit()


class DashboardPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.counts = {"total": 0, "suspicious": 0, "malicious": 0, "quarantined": 0}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(20)

        hdr = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)
        t = QLabel("Dashboard")
        t.setObjectName("title")
        s = QLabel("Surveillance temps réel de votre système")
        s.setObjectName("subtitle")
        left.addWidget(t)
        left.addWidget(s)
        hdr.addLayout(left)
        hdr.addStretch()
        self.status_lbl = QLabel("● ACTIF")
        self.status_lbl.setObjectName("status_on")
        hdr.addWidget(self.status_lbl)
        root.addLayout(hdr)

        div = QFrame()
        div.setObjectName("divider")
        root.addWidget(div)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.card_total = StatCard("Fichiers analysés", "0", TEXT_PRI, "🔍")
        self.card_susp  = StatCard("Suspects", "0", WARN, "⚠️")
        self.card_mal   = StatCard("Malveillants", "0", DANGER, "🚨")
        self.card_quar  = StatCard("En quarantaine", "0", ACCENT2, "🔒")
        for c in [self.card_total, self.card_susp, self.card_mal, self.card_quar]:
            stats_row.addWidget(c)
        root.addLayout(stats_row)

        feed_lbl = QLabel("Événements récents")
        feed_lbl.setStyleSheet(f"color: {TEXT_PRI}; font-weight: 600; font-size: 14px;")
        root.addWidget(feed_lbl)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.feed_container = QWidget()
        self.feed_layout = QVBoxLayout(self.feed_container)
        self.feed_layout.setContentsMargins(0, 0, 0, 0)
        self.feed_layout.setSpacing(6)

        self.empty_lbl = QLabel("Aucun événement — le système surveille en silence �")
        self.empty_lbl.setStyleSheet(f"color: {TEXT_SEC}; font-size: 13px;")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feed_layout.addWidget(self.empty_lbl)
        self.feed_layout.addStretch()

        self.scroll.setWidget(self.feed_container)
        root.addWidget(self.scroll, stretch=1)

    def add_event(self, ev: dict):
        self.empty_lbl.setVisible(False)
        self.counts["total"] += 1
        v = ev.get("verdict", "clean")
        if v == "suspicious":  self.counts["suspicious"] += 1
        if v == "malicious":   self.counts["malicious"] += 1
        if "quarantine" in ev.get("action", ""):
            self.counts["quarantined"] += 1

        self.card_total.update_value(str(self.counts["total"]))
        self.card_susp.update_value(str(self.counts["suspicious"]))
        self.card_mal.update_value(str(self.counts["malicious"]))
        self.card_quar.update_value(str(self.counts["quarantined"]))

        item = EventItem(ev.get("src_path", ""), v, ev.get("timestamp", int(time.time())))
        self.feed_layout.insertWidget(0, item)
        if self.feed_layout.count() > 102:
            w = self.feed_layout.takeAt(101)
            if w and w.widget():
                w.widget().deleteLater()


class QuarantinePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.quarantine_dir = os.path.join(os.path.expanduser("~"), "FileGuard", "quarantine")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)
        t = QLabel("Quarantaine")
        t.setObjectName("title")
        s = QLabel("Fichiers isolés et neutralisés")
        s.setObjectName("subtitle")
        left.addWidget(t)
        left.addWidget(s)
        hdr.addLayout(left)
        hdr.addStretch()
        refresh_btn = QPushButton("↻  Actualiser")
        refresh_btn.setObjectName("action_blue")
        refresh_btn.clicked.connect(self.load_events)
        hdr.addWidget(refresh_btn)
        root.addLayout(hdr)

        div = QFrame()
        div.setObjectName("divider")
        root.addWidget(div)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Fichier", "Verdict", "Score", "Raisons", "Date", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        root.addWidget(self.table)
        self.load_events()

    def load_events(self):
        self.table.setRowCount(0)
        meta = os.path.join(self.quarantine_dir, "events.jsonl")
        if not os.path.exists(meta):
            return
        with open(meta, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines):
            try:
                ev = json.loads(line.strip())
                if ev.get("action") != "quarantined":
                    continue
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setRowHeight(row, 44)

                self.table.setItem(row, 0, QTableWidgetItem(os.path.basename(ev.get("src_path", ""))))

                v = ev.get("verdict", "")
                v_item = QTableWidgetItem(v.upper())
                v_item.setForeground(QColor(WARN if v == "suspicious" else DANGER))
                v_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                self.table.setItem(row, 1, v_item)

                self.table.setItem(row, 2, QTableWidgetItem(str(ev.get("score", 0))))
                self.table.setItem(row, 3, QTableWidgetItem(", ".join(ev.get("reasons", []))))
                ts = ev.get("timestamp", 0)
                self.table.setItem(row, 4, QTableWidgetItem(datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")))

                del_btn = QPushButton("Supprimer")
                del_btn.setObjectName("danger")
                dst = ev.get("dst_path", "")
                del_btn.clicked.connect(lambda _, p=dst: self._delete_file(p))
                self.table.setCellWidget(row, 5, del_btn)
            except Exception:
                pass

    def _delete_file(self, path: str):
        try:
            if os.path.exists(path):
                os.remove(path)
            self.load_events()
        except Exception as e:
            print(f"[ERR] {e}")


class ScannerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.folder = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)
        t = QLabel("Scanner")
        t.setObjectName("title")
        s = QLabel("Analyse manuelle d'un dossier")
        s.setObjectName("subtitle")
        left.addWidget(t)
        left.addWidget(s)
        hdr.addLayout(left)
        hdr.addStretch()

        choose_btn = QPushButton("📂  Choisir un dossier")
        choose_btn.setObjectName("action_blue")
        choose_btn.clicked.connect(self._choose_folder)
        hdr.addWidget(choose_btn)

        self.scan_btn = QPushButton("▶  Lancer le scan")
        self.scan_btn.setObjectName("action")
        self.scan_btn.clicked.connect(self._start_scan)
        self.scan_btn.setEnabled(False)
        hdr.addWidget(self.scan_btn)
        root.addLayout(hdr)

        div = QFrame()
        div.setObjectName("divider")
        root.addWidget(div)

        self.folder_lbl = QLabel("Aucun dossier sélectionné")
        self.folder_lbl.setStyleSheet(f"color: {TEXT_SEC}; font-size: 12px; padding: 8px 0;")
        root.addWidget(self.folder_lbl)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet(f"color: {TEXT_SEC}; font-size: 12px;")
        root.addWidget(self.status_lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Fichier", "Verdict", "Score", "Raisons", "SHA-256"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        root.addWidget(self.table, stretch=1)

    def _choose_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Choisir un dossier à scanner")
        if f:
            self.folder = f
            self.folder_lbl.setText(f"📁  {f}")
            self.scan_btn.setEnabled(True)
            self.table.setRowCount(0)

    def _start_scan(self):
        if not self.folder:
            return
        self.table.setRowCount(0)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.scan_btn.setEnabled(False)
        self.worker = ScanWorker(self.folder)
        self.worker.progress.connect(self._on_progress)
        self.worker.result.connect(self._on_result)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_progress(self, current: int, total: int):
        self.progress.setValue(int(current / total * 100) if total > 0 else 0)
        self.status_lbl.setText(f"Analyse : {current} / {total} fichiers")

    def _on_result(self, ev: dict):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, 44)
        self.table.setItem(row, 0, QTableWidgetItem(os.path.basename(ev.get("src_path", ""))))
        v = ev.get("verdict", "")
        v_item = QTableWidgetItem(v.upper())
        v_item.setForeground(QColor(WARN if v == "suspicious" else DANGER))
        v_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.table.setItem(row, 1, v_item)
        self.table.setItem(row, 2, QTableWidgetItem(str(ev.get("score", 0))))
        self.table.setItem(row, 3, QTableWidgetItem(", ".join(ev.get("reasons", []))))
        sha = ev.get("sha256", "")
        self.table.setItem(row, 4, QTableWidgetItem(sha[:20] + "..." if len(sha) > 20 else sha))

    def _on_done(self):
        self.scan_btn.setEnabled(True)
        total = self.table.rowCount()
        self.status_lbl.setText(
            f"✅ Scan terminé — {total} menace(s) détectée(s)" if total
            else "✅ Scan terminé — aucune menace détectée"
        )
        self.progress.setValue(100)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Watchdog")
        self.setMinimumSize(1100, 680)
        self.setStyleSheet(stylesheet())
        self._build_ui()
        self._start_log_watcher()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 20, 12, 20)
        side_layout.setSpacing(4)

        logo_row = QHBoxLayout()
        shield = QLabel("🐕")
        shield.setStyleSheet("font-size: 22px;")
        name = QLabel("Watchdog")
        name.setStyleSheet(f"color: {TEXT_PRI}; font-size: 16px; font-weight: 700;")
        version = QLabel("v2.0")
        version.setStyleSheet(f"color: {TEXT_SEC}; font-size: 11px;")
        logo_row.addWidget(shield)
        logo_row.addWidget(name)
        logo_row.addWidget(version)
        logo_row.addStretch()
        side_layout.addLayout(logo_row)
        side_layout.addSpacing(16)

        div = QFrame()
        div.setObjectName("divider")
        side_layout.addWidget(div)
        side_layout.addSpacing(8)

        self.nav_buttons = []
        for label, idx in [("🏠  Dashboard", 0), ("🔒  Quarantaine", 1), ("🔍  Scanner", 2)]:
            btn = QPushButton(label)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.setChecked(idx == 0)
            btn.clicked.connect(lambda _, i=idx: self._switch_page(i))
            self.nav_buttons.append(btn)
            side_layout.addWidget(btn)

        side_layout.addStretch()

        div2 = QFrame()
        div2.setObjectName("divider")
        side_layout.addWidget(div2)
        side_layout.addSpacing(8)

        watcher_row = QHBoxLayout()
        watcher_lbl = QLabel("Watcher")
        watcher_lbl.setStyleSheet(f"color: {TEXT_SEC}; font-size: 12px;")
        self.watcher_status = QLabel("● ON")
        self.watcher_status.setObjectName("status_on")
        watcher_row.addWidget(watcher_lbl)
        watcher_row.addStretch()
        watcher_row.addWidget(self.watcher_status)
        side_layout.addLayout(watcher_row)
        main.addWidget(sidebar)

        # Pages
        self.pages = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.quarantine_page = QuarantinePage()
        self.scanner_page = ScannerPage()
        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.quarantine_page)
        self.pages.addWidget(self.scanner_page)
        main.addWidget(self.pages, stretch=1)

    def _switch_page(self, idx: int):
        self.pages.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == idx)
        if idx == 1:
            self.quarantine_page.load_events()

    def _start_log_watcher(self):
        jsonl = os.path.join(os.path.expanduser("~"), "FileGuard", "quarantine", "events.jsonl")
        self.log_watcher = LogWatcher(jsonl)
        self.log_watcher.new_event.connect(self.dashboard_page.add_event)
        self.log_watcher.start()

    def closeEvent(self, event):
        self.log_watcher.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Watchdog")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
