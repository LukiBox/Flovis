"""Zakladka: Raport - interpretacja AI i eksport PDF."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QPushButton, QTextEdit, QLabel, QComboBox,
                               QFileDialog, QMessageBox)
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QTextCursor

from ...core.ai import ollama_client
from ...core.report import build_report


class _AIWorker(QThread):
    chunk = Signal(str)
    thinking = Signal(str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, payload, model, preset):
        super().__init__()
        self.payload, self.model, self.preset = payload, model, preset

    def run(self):
        try:
            text = ""
            for kind, part in ollama_client.interpret_stream(
                    self.payload, self.model, preset=self.preset):
                if kind == "thinking":
                    self.thinking.emit(part)
                else:
                    text += part
                    self.chunk.emit(part)
            self.done.emit(text)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class ReportTab(QWidget):
    def __init__(self, app_state):
        super().__init__()
        self.state = app_state
        self.ai_text = ""
        self._build()

    def _build(self):
        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.model_cb = QComboBox()
        self._refresh_models()
        bar.addWidget(QLabel("Model AI:"))
        bar.addWidget(self.model_cb, 1)
        b_refresh = QPushButton("Odswiez modele"); b_refresh.setProperty("flat", True)
        b_refresh.clicked.connect(self._refresh_models)
        bar.addWidget(b_refresh)
        root.addLayout(bar)

        bar2 = QHBoxLayout()
        bar2.addWidget(QLabel("Rodzaj analizy:"))
        self.preset_cb = QComboBox()
        for key, (label, _) in ollama_client.PRESETS.items():
            self.preset_cb.addItem(label, key)
        bar2.addWidget(self.preset_cb, 1)
        root.addLayout(bar2)

        self.b_ai = QPushButton("Generuj interpretacje AI")
        self.b_ai.clicked.connect(self._run_ai)
        root.addWidget(self.b_ai)
        self.ai_status = QLabel(""); self.ai_status.setObjectName("hint")
        self.ai_status.setWordWrap(True)
        root.addWidget(self.ai_status)

        box = QGroupBox("Interpretacja slowna")
        bl = QVBoxLayout(box)
        self.text = QTextEdit()
        self.text.setPlaceholderText(
            "Tu pojawi sie interpretacja wynikow z modelu Ollama.\n"
            "Mozesz tez wpisac/poprawic tekst recznie przed eksportem.")
        bl.addWidget(self.text)
        root.addWidget(box, 1)

        exp = QHBoxLayout()
        b_pdf = QPushButton("Eksportuj raport PDF")
        b_pdf.clicked.connect(self._export_pdf)
        exp.addStretch(); exp.addWidget(b_pdf)
        root.addLayout(exp)

    def _refresh_models(self):
        self.model_cb.clear()
        models = ollama_client.list_models()
        if models:
            self.model_cb.addItems(models)
            idx = self.model_cb.findText(ollama_client.DEFAULT_MODEL)
            if idx >= 0:
                self.model_cb.setCurrentIndex(idx)
        else:
            self.model_cb.addItem(ollama_client.DEFAULT_MODEL + " (offline)")

    def _payload(self):
        res = self.state.current_result
        if res is None:
            return None
        return ollama_client.build_context(
            res, model=self.state.current_model,
            polar2d=self.state.current_polar2d)

    def _run_ai(self):
        payload = self._payload()
        if payload is None:
            QMessageBox.warning(self, "Brak wynikow",
                                "Najpierw uruchom analize.")
            return
        if not ollama_client.is_available():
            QMessageBox.information(
                self, "Ollama offline",
                "Nie wykryto Ollama na localhost:11434.\n"
                "Uruchom 'ollama serve', a nastepnie sprobuj ponownie.")
            return
        model = self.model_cb.currentText().split(" ")[0]
        if not ollama_client.model_available(model):
            QMessageBox.information(self, "Brak modelu",
                                    ollama_client.missing_model_hint(model))
            return
        self.text.clear(); self.ai_text = ""
        self._think_chars = 0
        self._got_content = False
        self.b_ai.setEnabled(False); self.b_ai.setText("Generowanie...")
        self.ai_status.setStyleSheet("color:#2563eb;")
        self.ai_status.setText(
            "Model AI analizuje dane... Duze modele (np. qwen3:30b) moga myslec "
            "nawet ~1-2 min zanim zaczna pisac. Prosze czekac.")
        self.state.status("Generowanie interpretacji AI...")
        # licznik czasu, zeby bylo widac ze aplikacja pracuje
        import time
        from PySide6.QtCore import QTimer
        self._ai_t0 = time.time()
        self._ai_timer = QTimer(self)
        self._ai_timer.timeout.connect(self._tick_ai)
        self._ai_timer.start(1000)
        preset = self.preset_cb.currentData()
        self.worker = _AIWorker(payload, model, preset)
        self.worker.chunk.connect(self._append)
        self.worker.thinking.connect(self._on_thinking)
        self.worker.done.connect(self._ai_done)
        self.worker.failed.connect(self._ai_failed)
        self.worker.start()

    def _tick_ai(self):
        import time
        s = int(time.time() - self._ai_t0)
        if not self._got_content:
            extra = f" (analiza: {self._think_chars} znakow rozumowania)" if self._think_chars else ""
            self.ai_status.setText(
                f"Model AI pracuje... {s} s{extra}. Odpowiedz pojawi sie ponizej.")

    def _on_thinking(self, part):
        self._think_chars += len(part)

    def _append(self, part):
        if not self._got_content:
            self._got_content = True
            self.ai_status.setStyleSheet("color:#059669;")
            self.ai_status.setText("Model pisze odpowiedz...")
        self.text.moveCursor(QTextCursor.MoveOperation.End)
        self.text.insertPlainText(part)

    def _ai_done(self, text):
        self.ai_text = text
        self._ai_timer.stop()
        self.b_ai.setEnabled(True); self.b_ai.setText("Generuj interpretacje AI")
        if not text.strip():
            self.ai_status.setStyleSheet("color:#d97706;")
            self.ai_status.setText(
                "Model nie zwrocil tekstu. Sprobuj innego modelu (lista wyzej) "
                "lub presetu 'Krotka ocena'.")
        else:
            self.ai_status.setStyleSheet("color:#059669;")
            self.ai_status.setText("Interpretacja gotowa. Mozesz ja edytowac przed eksportem.")
        self.state.status("Interpretacja gotowa.")

    def _ai_failed(self, msg):
        self._ai_timer.stop()
        self.b_ai.setEnabled(True); self.b_ai.setText("Generuj interpretacje AI")
        self.ai_status.setStyleSheet("color:#dc2626;")
        self.ai_status.setText("Blad generowania AI.")
        QMessageBox.critical(self, "Blad AI", msg)

    def _export_pdf(self):
        res = self.state.current_result
        if res is None:
            QMessageBox.warning(self, "Brak wynikow", "Najpierw uruchom analize.")
            return
        fn, _ = QFileDialog.getSaveFileName(
            self, "Zapisz raport", f"Flovis_{res.model_name}.pdf",
            "PDF (*.pdf)")
        if not fn:
            return
        try:
            build_report(res, fn, model=self.state.current_model,
                         ai_text=self.text.toPlainText().strip() or None,
                         airfoil=self.state.current_airfoil,
                         polar2d=self.state.current_polar2d,
                         thumbnail_png=self._thumbnail())
            QMessageBox.information(self, "Gotowe", f"Raport zapisany:\n{fn}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Blad eksportu", str(e))

    def _thumbnail(self):
        """Best-effort miniatura 3D do strony tytulowej (pomijana, gdy brak VTK)."""
        if self.state.current_model is None:
            return None
        try:
            import tempfile, os
            from ..widgets.model3d_view import Model3DView
            view = Model3DView(off_screen=True)
            view.set_model(self.state.current_model)
            if self.state.current_result is not None:
                view.show_result(self.state.current_result)
            tmp = os.path.join(tempfile.gettempdir(), "flovis_thumb.png")
            view.screenshot(tmp)
            view.close()
            with open(tmp, "rb") as f:
                return f.read()
        except Exception:  # noqa: BLE001
            return None
