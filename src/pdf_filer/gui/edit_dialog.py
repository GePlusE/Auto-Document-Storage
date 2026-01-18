from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QComboBox,
    QFormLayout,
)

from .types import PlanItem
from .validators import (
    validate_folder_name,
    validate_filename_stem,
    compute_collision_preview,
)


class EditDecisionDialog(QDialog):
    """
    Edit filename label + folder with:
      - Live validation (F25)
      - Collision preview (F26)
      - Quick actions: reset / fallback (F28)
      - Accept/Reject per file (F04/F05)
    """

    def __init__(self, parent, cfg, item: PlanItem):
        super().__init__(parent)
        self.cfg = cfg
        self.item = item

        self.setWindowTitle(f"Edit: {item.original_filename}")
        self.resize(720, 320)

        lay = QVBoxLayout(self)

        info = QLabel(
            f"<b>{item.original_filename}</b><br>"
            f"Sender: {item.sender} | Conf: {item.conf_final:.2f} | Stage: {item.stage_used}"
        )
        info.setTextFormat(Qt.RichText)
        lay.addWidget(info)

        form = QFormLayout()
        self.ed_label = QLineEdit(self)
        self.ed_folder = QLineEdit(self)

        # F29 Naming templates
        self.cb_template = QComboBox(self)
        self.ed_template = QLineEdit(self)
        self.ed_template.setPlaceholderText(
            "Custom template… e.g. {{sender}}_{{doctype}}  (tokens: {{date}}, {{sender}}, {{doctype}}, {{folder}}, {{label}})"
        )

        # Default templates (you can extend later)
        self.templates = [
            ("Default (label + folder)", "{{label}} {{folder}}"),
            ("{{sender}} {{doctype}}", "{{sender}} {{doctype}}"),
            ("{{doctype}} {{folder}}", "{{doctype}} {{folder}}"),
            ("{{date}}_{{sender}}_{{doctype}}", "{{date}}_{{sender}}_{{doctype}}"),
            ("Custom…", "__custom__"),
        ]
        for name, tpl in self.templates:
            self.cb_template.addItem(name, tpl)

        # prefill with current effective values
        self.ed_label.setText(
            item.edited_filename_stem or item.filename_label or "Dokument"
        )
        self.ed_folder.setText(item.edited_folder or item.target_folder or "")

        form.addRow("Filename label", self.ed_label)
        form.addRow("Target folder", self.ed_folder)
        form.addRow("Naming template", self.cb_template)
        form.addRow("Custom template", self.ed_template)

        lay.addLayout(form)

        # Buttons row
        btns = QHBoxLayout()
        self.btn_reset = QPushButton("Reset to suggestion")
        self.btn_fallback = QPushButton(
            f"Use fallback ({self.cfg.paths.fallback_dir.name})"
        )
        self.btn_accept = QPushButton("Accept")
        self.btn_reject = QPushButton("Reject")
        self.btn_close = QPushButton("Close")

        btns.addWidget(self.btn_reset)
        btns.addWidget(self.btn_fallback)
        btns.addStretch(1)
        btns.addWidget(self.btn_accept)
        btns.addWidget(self.btn_reject)
        btns.addWidget(self.btn_close)
        lay.addLayout(btns)

        self.lbl_validation = QLabel("")
        self.lbl_preview = QLabel("")
        self.lbl_preview.setTextFormat(Qt.RichText)
        lay.addWidget(self.lbl_validation)
        lay.addWidget(self.lbl_preview)

        # hooks
        self.btn_reset.clicked.connect(self.on_reset)
        self.btn_fallback.clicked.connect(self.on_fallback)
        self.btn_accept.clicked.connect(self.on_accept)
        self.btn_reject.clicked.connect(self.on_reject)
        self.btn_close.clicked.connect(self.reject)

        self.ed_label.textChanged.connect(self.refresh_preview)
        self.ed_folder.textChanged.connect(self.refresh_preview)

        # Prefill template (use item's stored template if any)
        if (self.item.naming_template or "").strip():
            self.cb_template.setCurrentIndex(self.cb_template.count() - 1)  # Custom…
            self.ed_template.setText(self.item.naming_template)
        else:
            self.cb_template.setCurrentIndex(0)
            self.ed_template.setText("")

        self.cb_template.currentIndexChanged.connect(self.on_template_changed)
        self.on_template_changed()

        self.refresh_preview()

    def on_reset(self):
        self.ed_label.setText(self.item.filename_label or "Dokument")
        self.ed_folder.setText(self.item.target_folder or "")
        self.refresh_preview()

    def on_fallback(self):
        self.ed_folder.setText(self.cfg.paths.fallback_dir.name)
        self.refresh_preview()

    def on_template_changed(self):
        tpl = self.cb_template.currentData()
        is_custom = tpl == "__custom__"
        self.ed_template.setEnabled(is_custom)
        self.refresh_preview()

    def refresh_preview(self):
        label = self.ed_label.text()
        folder = self.ed_folder.text()

        errors: List[str] = []
        errors += validate_filename_stem(
            label, max_len=self.cfg.renaming.filename_max_len
        )
        errors += validate_folder_name(folder)

        if errors:
            self.lbl_validation.setText("❌ " + " | ".join(errors))
            self.btn_accept.setEnabled(False)
        else:
            self.lbl_validation.setText("✅ OK")
            self.btn_accept.setEnabled(True)

        # Collision preview
        try:
            date_prefix = (
                self.item.planned_target_path.name.split(" ", 1)[0]
                if self.item.planned_target_path
                else "0000-00-00"
            )
            selected = self.cb_template.currentData()
            template = (
                self.ed_template.text().strip()
                if selected == "__custom__"
                else (selected or "")
            )
            planned, note = compute_collision_preview(
                cfg=self.cfg,
                pdf_path=self.item.input_path,
                date_prefix=self.item.date_prefix or date_prefix,
                folder=folder,
                filename_label=label,
                template=template,
                sender=self.item.sender,
                doctype=self.item.document_type,
            )

            txt = f"<b>Preview:</b> {planned}<br>"
            if note:
                txt += f"<span style='color:#b36b00'>⚠ {note}</span>"
            self.lbl_preview.setText(txt)
        except Exception as e:
            self.lbl_preview.setText(f"<b>Preview error:</b> {e}")

    def on_accept(self):
        label = self.ed_label.text().strip()
        folder = self.ed_folder.text().strip()

        # Validate again
        errors: List[str] = []
        errors += validate_filename_stem(
            label, max_len=self.cfg.renaming.filename_max_len
        )
        errors += validate_folder_name(folder)
        if errors:
            QMessageBox.warning(self, "Invalid input", "\n".join(errors))
            return

        # Compute new planned target path now (so apply is deterministic)
        date_prefix = (
            self.item.planned_target_path.name.split(" ", 1)[0]
            if self.item.planned_target_path
            else "0000-00-00"
        )
        selected = self.cb_template.currentData()
        template = (
            self.ed_template.text().strip()
            if selected == "__custom__"
            else (selected or "")
        )

        planned, _note = compute_collision_preview(
            cfg=self.cfg,
            pdf_path=self.item.input_path,
            date_prefix=self.item.date_prefix or date_prefix,
            folder=folder,
            filename_label=label,
            template=template,
            sender=self.item.sender,
            doctype=self.item.document_type,
        )

        self.item.edited_filename_stem = label
        self.item.edited_folder = folder
        self.item.target_folder = folder
        self.item.planned_target_path = planned
        self.item.naming_template = template
        self.item.status = "Accepted"
        self.accept()

    def on_reject(self):
        self.item.status = "Rejected"
        self.accept()
