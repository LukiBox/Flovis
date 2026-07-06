"""Tab: Report - AI interpretation and PDF export."""
from __future__ import annotations

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QPushButton, QTextEdit, QLabel, QComboBox,
                               QFileDialog, QMessageBox)
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QTextCursor

from ...core.ai import ollama_client
from ...core.report import build_report
from ...core.i18n import t


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
        bar.addWidget(QLabel(t("AI model:")))
        bar.addWidget(self.model_cb, 1)
        b_refresh = QPushButton(t("Refresh models")); b_refresh.setProperty("flat", True)
        b_refresh.clicked.connect(self._refresh_models)
        bar.addWidget(b_refresh)
        root.addLayout(bar)

        bar2 = QHBoxLayout()
        bar2.addWidget(QLabel(t("Analysis type:")))
        self.preset_cb = QComboBox()
        for key, (label, _) in ollama_client.PRESETS.items():
            self.preset_cb.addItem(t(label), key)
        bar2.addWidget(self.preset_cb, 1)
        root.addLayout(bar2)

        self.b_ai = QPushButton(t("Generate AI interpretation"))
        self.b_ai.clicked.connect(self._run_ai)
        root.addWidget(self.b_ai)
        self.ai_status = QLabel(""); self.ai_status.setObjectName("hint")
        self.ai_status.setWordWrap(True)
        root.addWidget(self.ai_status)

        box = QGroupBox(t("Written interpretation"))
        bl = QVBoxLayout(box)
        self.text = QTextEdit()
        self.text.setPlaceholderText(
            t("The interpretation from the Ollama model will appear here.\n"
              "You can also type/edit the text manually before export."))
        bl.addWidget(self.text)
        root.addWidget(box, 1)

        exp = QHBoxLayout()
        b_pdf = QPushButton(t("Export PDF report"))
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
            QMessageBox.warning(self, t("No results"),
                                t("Run an analysis first."))
            return
        if not ollama_client.is_available():
            QMessageBox.information(
                self, t("Ollama offline"),
                t("Ollama was not found at localhost:11434.\n"
                  "Start 'ollama serve' and try again."))
            return
        model = self.model_cb.currentText().split(" ")[0]
        if not ollama_client.model_available(model):
            QMessageBox.information(self, t("Model missing"),
                                    ollama_client.missing_model_hint(model))
            return
        self.text.clear(); self.ai_text = ""
        self._think_chars = 0
        self._got_content = False
        self.b_ai.setEnabled(False); self.b_ai.setText(t("Generating..."))
        self.ai_status.setStyleSheet("color:#2563eb;")
        self.ai_status.setText(
            t("The AI model is analyzing the data... Large models (e.g. qwen3:30b) "
              "may think for ~1-2 min before writing. Please wait."))
        self.state.status(t("Generating AI interpretation..."))
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
            extra = (t(" (reasoning: {} chars)").format(self._think_chars)
                     if self._think_chars else "")
            self.ai_status.setText(
                t("The AI model is working... {s} s{extra}. "
                  "The answer will appear below.").format(s=s, extra=extra))

    def _on_thinking(self, part):
        self._think_chars += len(part)

    def _append(self, part):
        if not self._got_content:
            self._got_content = True
            self.ai_status.setStyleSheet("color:#059669;")
            self.ai_status.setText(t("The model is writing the answer..."))
        self.text.moveCursor(QTextCursor.MoveOperation.End)
        self.text.insertPlainText(part)

    def _ai_done(self, text):
        self.ai_text = text
        self._ai_timer.stop()
        self.b_ai.setEnabled(True); self.b_ai.setText(t("Generate AI interpretation"))
        if not text.strip():
            self.ai_status.setStyleSheet("color:#d97706;")
            self.ai_status.setText(
                t("The model returned no text. Try another model (list above) "
                  "or the 'Short assessment' preset."))
        else:
            self.ai_status.setStyleSheet("color:#059669;")
            self.ai_status.setText(t("Interpretation ready. You can edit it before export."))
        self.state.status(t("Interpretation ready."))

    def _ai_failed(self, msg):
        self._ai_timer.stop()
        self.b_ai.setEnabled(True); self.b_ai.setText(t("Generate AI interpretation"))
        self.ai_status.setStyleSheet("color:#dc2626;")
        self.ai_status.setText(t("AI generation error."))
        QMessageBox.critical(self, t("AI error"), msg)

    def _export_pdf(self):
        res = self.state.current_result
        if res is None:
            QMessageBox.warning(self, t("No results"), t("Run an analysis first."))
            return
        fn, _ = QFileDialog.getSaveFileName(
            self, t("Save report"), f"Flovis_{res.model_name}.pdf",
            "PDF (*.pdf)")
        if not fn:
            return
        try:
            build_report(res, fn, model=self.state.current_model,
                         ai_text=self.text.toPlainText().strip() or None,
                         airfoil=self.state.current_airfoil,
                         polar2d=self.state.current_polar2d,
                         thumbnail_png=self._thumbnail())
            QMessageBox.information(self, t("Done"),
                                    t("Report saved:\n{}").format(fn))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, t("Export error"), str(e))

    def _thumbnail(self):
        """Best-effort 3D thumbnail for the title page (skipped if VTK missing)."""
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
