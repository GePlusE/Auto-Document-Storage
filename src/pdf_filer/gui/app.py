from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import math

from PySide6.QtCore import Qt, QSortFilterProxyModel, QSettings, QModelIndex
from PySide6.QtGui import (
    QStandardItemModel,
    QStandardItem,
    QAction,
    QKeySequence,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QTextEdit,
    QHeaderView,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QComboBox,
    QSplitter,
    QTableView,
    QLabel,
    QSpinBox,
    QSlider,
    QMessageBox,
    QCheckBox,
    QDockWidget,
    QListWidget,
    QListWidgetItem,
)

from .analyzer import list_input_pdfs, analyze_pdf
from .preview import PdfPreview
from .state import SessionState
from .mapping_editor import MappingEditorDialog
from .edit_dialog import EditDecisionDialog
from .diff_dialog import DryRunDiffDialog


class PlanProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search = ""
        self.filter_mode = "All"
        self.fallback_name = "_Unklar"

    def set_search(self, s: str):
        self.search = (s or "").lower().strip()
        self.invalidateFilter()

    def set_filter_mode(self, mode: str):
        self.filter_mode = mode
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        m = self.sourceModel()
        # columns: File, Sender, Conf, Folder, NewName, Status, Error
        file_ = (m.item(source_row, 0).text() or "").lower()
        sender = (m.item(source_row, 1).text() or "").lower()
        folder = (m.item(source_row, 3).text() or "").lower()
        status = m.item(source_row, 5).text() or ""
        err = (m.item(source_row, 6).text() or "").lower()
        conf = float(m.item(source_row, 2).text() or 0.0)

        if self.search:
            hay = " ".join([file_, sender, folder, status.lower(), err])
            if self.search not in hay:
                return False

        if self.filter_mode == "Only _Unklar":
            fb = (self.fallback_name or "").lower()
            return folder.lower() == fb
        if self.filter_mode == "Only Errors":
            return status == "Error" or bool(err)
        if self.filter_mode == "Only Low Conf":
            return conf < 0.70
        if self.filter_mode == "Only Pending":
            return status == "Pending"

        return True


class MainWindow(QMainWindow):
    def __init__(self, cfg, mapper, client, logger):
        super().__init__()
        self.cfg = cfg
        self.mapper = mapper
        self.client = client
        self.logger = logger
        self.state = SessionState(cfg)

        self.settings = QSettings("gepluse", "pdf-filer-gui")

        self.setWindowTitle("pdf-filer GUI")
        self.resize(1300, 800)

        self.preview: Optional[PdfPreview] = None
        self.preview_page = 0
        self.preview_zoom = 1.0
        self.sensitive_mode = False

        # Models
        self.model = QStandardItemModel(0, 7)
        self.model.setHorizontalHeaderLabels(
            ["File", "Sender", "Conf", "Folder", "New filename", "Status", "Error"]
        )

        self.proxy = PlanProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.fallback_name = self.cfg.paths.fallback_dir.name
        self.proxy.setSortCaseSensitivity(Qt.CaseInsensitive)

        # UI
        root = QWidget()
        root_lay = QVBoxLayout(root)

        # Top controls
        top = QHBoxLayout()
        self.btn_dry = QPushButton("Dry-Run (Analyze)")
        self.btn_accept = QPushButton("Accept selected")
        self.btn_reject = QPushButton("Reject selected")
        self.btn_to_fallback = QPushButton(
            f"Move selected to {self.cfg.paths.fallback_dir.name}"
        )
        self.btn_apply = QPushButton("Apply accepted")
        self.btn_undo = QPushButton("Undo last")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search… (file/sender/folder/status)")
        self.filter = QComboBox()
        self.filter.addItems(
            ["All", "Only _Unklar", "Only Errors", "Only Low Conf", "Only Pending"]
        )
        self.chk_sensitive = QCheckBox("Sensitive mode (blur)")
        self.chk_sensitive.setChecked(False)

        self.btn_dry.clicked.connect(self.on_dry_run)
        self.btn_accept.clicked.connect(lambda: self._batch("accept"))
        self.btn_reject.clicked.connect(lambda: self._batch("reject"))
        self.btn_to_fallback.clicked.connect(lambda: self._batch("fallback"))
        self.btn_apply.clicked.connect(self.on_apply)
        self.btn_undo.clicked.connect(self.on_undo)
        self.search.textChanged.connect(self.proxy.set_search)
        self.filter.currentTextChanged.connect(self.proxy.set_filter_mode)
        self.chk_sensitive.toggled.connect(self.on_sensitive_toggle)

        top.addWidget(self.btn_dry)
        top.addWidget(self.btn_accept)
        top.addWidget(self.btn_reject)
        top.addWidget(self.btn_to_fallback)
        top.addWidget(self.btn_apply)
        top.addWidget(self.btn_undo)
        top.addSpacing(10)
        top.addWidget(self.search, 1)
        top.addWidget(self.filter)
        top.addWidget(self.chk_sensitive)
        root_lay.addLayout(top)

        # --- Main area layout ---
        # Row 1: PDF table full width
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.ExtendedSelection)  # Multi-select (F07)
        self.table.setSortingEnabled(True)  # Sorting (F10)
        self.table.doubleClicked.connect(self.on_double_click_edit)
        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)

        # Auto-size columns (optimal width on startup + after refresh_table)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(True)

        # Row 2: Preview + LLM Explanation side-by-side
        self.mid_split = QSplitter(Qt.Horizontal)
        self.mid_split.setChildrenCollapsible(False)

        # --- Preview area (left of row 2) ---
        preview_wrap = QWidget()
        preview_lay = QVBoxLayout(preview_wrap)

        prev_controls = QHBoxLayout()
        self.lbl_prev = QLabel("Preview")
        self.btn_prev = QPushButton("Prev")
        self.btn_next = QPushButton("Next")
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self.on_page_spin)

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setMinimum(25)
        self.zoom_slider.setMaximum(300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.on_zoom)

        self.btn_prev.clicked.connect(lambda: self.set_page(self.preview_page - 1))
        self.btn_next.clicked.connect(lambda: self.set_page(self.preview_page + 1))

        self.btn_reveal = QPushButton("Reveal")
        self.btn_reveal.clicked.connect(self.on_reveal)

        prev_controls.addWidget(self.lbl_prev, 1)
        prev_controls.addWidget(self.btn_prev)
        prev_controls.addWidget(self.btn_next)
        prev_controls.addWidget(QLabel("Page"))
        prev_controls.addWidget(self.page_spin)
        prev_controls.addWidget(QLabel("Zoom"))
        prev_controls.addWidget(self.zoom_slider)
        prev_controls.addWidget(self.btn_reveal)

        preview_lay.addLayout(prev_controls)

        preview_row = QHBoxLayout()
        self.thumb_list = QListWidget()
        self.thumb_list.setMaximumWidth(220)
        self.thumb_list.itemClicked.connect(self.on_thumb_clicked)

        self.preview_label = QLabel("Select a PDF…")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(600, 500)

        preview_row.addWidget(self.thumb_list)
        preview_row.addWidget(self.preview_label, 1)
        preview_lay.addLayout(preview_row, 1)

        # --- LLM Explanation (right of row 2) ---
        self.llm_box = QGroupBox("LLM Explanation")
        llm_lay = QVBoxLayout(self.llm_box)
        llm_lay.setContentsMargins(8, 8, 8, 8)

        self.llm_text = QTextEdit()
        self.llm_text.setReadOnly(True)
        self.llm_text.setAcceptRichText(True)
        self.llm_text.setHtml("Select a PDF…")
        llm_lay.addWidget(self.llm_text)

        self.mid_split.addWidget(preview_wrap)
        self.mid_split.addWidget(self.llm_box)
        self.mid_split.setSizes([850, 350])
        saved_mid = self.settings.value("mid_split_sizes")
        if saved_mid:
            try:
                self.mid_split.setSizes([int(x) for x in saved_mid])
            except Exception:
                pass

        # Vertical splitter: table height adjustable (user can drag)
        self.v_split = QSplitter(Qt.Vertical)
        self.v_split.setChildrenCollapsible(False)

        self.v_split.addWidget(self.table)
        self.v_split.addWidget(self.mid_split)

        self.v_split.setSizes([260, 540])
        saved = self.settings.value("v_split_sizes")
        if saved:
            try:
                self.v_split.setSizes([int(x) for x in saved])
            except Exception:
                pass

        root_lay.addWidget(self.v_split, 1)

        self.setCentralWidget(root)

        # History dock (F14)
        self.history_dock = QDockWidget("Action History", self)
        self.history_dock.setObjectName("dock_action_history")
        self.history_list = QListWidget()
        self.history_dock.setWidget(self.history_list)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.history_dock)

        # Menu actions
        act_open_mapping = QAction("Open Mapping Editor…", self)
        act_open_mapping.triggered.connect(self.open_mapping_editor)

        act_diff = QAction("Show dry-run diff…", self)
        act_diff.triggered.connect(self.show_diff_dialog)

        act_reveal = QAction("Reveal selected in Finder", self)
        act_reveal.triggered.connect(self.reveal_selected)
        act_reveal.setShortcut(QKeySequence("Cmd+R"))

        act_reset_layout = QAction("Reset layout", self)
        act_reset_layout.triggered.connect(self.reset_layout)

        menu_file = self.menuBar().addMenu("File")
        menu_file.addAction(act_reveal)

        menu_tools = self.menuBar().addMenu("Tools")
        menu_tools.addAction(act_open_mapping)
        menu_tools.addAction(act_diff)

        # View menu: toggle docks
        menu_view = self.menuBar().addMenu("View")

        act_toggle_llm = QAction("LLM Explanation", self)
        act_toggle_llm.setCheckable(True)
        act_toggle_llm.setChecked(True)
        act_toggle_llm.toggled.connect(self.llm_box.setVisible)
        menu_view.addAction(act_toggle_llm)

        menu_view.addAction(self.history_dock.toggleViewAction())

        menu_view.addSeparator()
        menu_view.addAction(act_reset_layout)

        # Restore layout (F54)
        if self.settings.value("geom"):
            self.restoreGeometry(self.settings.value("geom"))
        if self.settings.value("state"):
            self.restoreState(self.settings.value("state"))

        self.table.resizeColumnsToContents()

    def closeEvent(self, event):
        self.settings.setValue("geom", self.saveGeometry())
        self.settings.setValue("state", self.saveState())
        try:
            if self.preview:
                self.preview.close()
        except Exception:
            pass
        try:
            self.settings.setValue("v_split_sizes", self.v_split.sizes())
        except Exception:
            pass

        try:
            self.settings.setValue("mid_split_sizes", self.mid_split.sizes())
        except Exception:
            pass

        super().closeEvent(event)

    def on_sensitive_toggle(self, checked: bool):
        self.sensitive_mode = bool(checked)
        self.render_preview()

    def on_reveal(self):
        self.sensitive_mode = False
        self.chk_sensitive.setChecked(False)
        self.render_preview()

    def open_mapping_editor(self):
        dlg = MappingEditorDialog(self, mapping_path=self.cfg.paths.mapping_json)
        dlg.exec()

    def on_dry_run(self):
        pdfs = list_input_pdfs(self.cfg.paths.input_dir)
        items = []
        for p in pdfs:
            it = analyze_pdf(p, self.cfg, self.mapper, self.client, self.logger)
            items.append(it)
        self.state.set_items(items)
        self.refresh_table()
        self.refresh_history()

    def refresh_history(self):
        self.history_list.clear()
        for h in self.state.history[-200:]:
            self.history_list.addItem(f"{h.ts} | {h.action} | {h.file} | {h.details}")

    def refresh_table(self):
        self.model.removeRows(0, self.model.rowCount())
        for it in self.state.items:
            folder = it.effective_folder() or it.target_folder
            newname = it.planned_target_path.name if it.planned_target_path else ""
            err = it.error or ""
            row = [
                QStandardItem(it.original_filename),
                QStandardItem(it.sender),
                QStandardItem(f"{it.conf_final:.2f}"),
                QStandardItem(folder),
                QStandardItem(newname),
                QStandardItem(it.status),
                QStandardItem(err),
            ]
            for c in row:
                c.setEditable(False)
            self.model.appendRow(row)
        self.table.resizeColumnsToContents()

    def selected_source_rows(self) -> List[int]:
        sel = self.table.selectionModel().selectedRows()
        rows = []
        for idx in sel:
            src = self.proxy.mapToSource(idx)
            rows.append(src.row())
        return sorted(set(rows))

    def _batch(self, what: str):
        rows = self.selected_source_rows()
        if not rows:
            return
        if what == "accept":
            self.state.accept(rows)
        elif what == "reject":
            self.state.reject(rows)
        elif what == "fallback":
            self.state.move_to_fallback(rows)
        self.refresh_table()
        self.refresh_history()

    def on_apply(self):
        rows = list(range(len(self.state.items)))
        self.state.apply_selected(rows, dry_run=False)
        self.refresh_table()
        self.refresh_history()

    def on_undo(self):
        self.state.undo_last()
        self.refresh_table()
        self.refresh_history()

    def reveal_selected(self):
        rows = self.selected_source_rows()
        if not rows:
            return
        it = self.state.items[rows[0]]
        self.state.reveal_in_finder(it.input_path)

    def show_diff_dialog(self):
        rows = self.selected_source_rows()
        if not rows:
            items = self.state.items
        else:
            items = [self.state.items[i] for i in rows]
        dlg = DryRunDiffDialog(self, items)
        dlg.exec()

    def reset_layout(self):
        # History dock visible and docked bottom
        self.history_dock.show()
        self.addDockWidget(Qt.BottomDockWidgetArea, self.history_dock)

        # LLM panel visible
        try:
            self.llm_box.setVisible(True)
        except Exception:
            pass

        # Reset splitters to defaults
        try:
            self.v_split.setSizes([260, 540])
        except Exception:
            pass
        try:
            self.mid_split.setSizes([850, 350])  # LLM enger default
        except Exception:
            pass

    # Editing (F05, F25, F26, F28, F30 light)
    def on_double_click_edit(self, index: QModelIndex):
        src = self.proxy.mapToSource(index)
        row = src.row()
        if row < 0 or row >= len(self.state.items):
            return
        it = self.state.items[row]

        dlg = EditDecisionDialog(self, self.cfg, it)
        dlg.exec()

        # History + UI refresh
        self.state.history.append(
            type(self.state.history[0])(
                self.state._now(), "Edit", it.original_filename, f"status={it.status}"
            )
        )
        self.refresh_table()
        self.refresh_history()
        self.update_why_panel(it)

    # Preview
    def on_selection_changed(self, *_):
        rows = self.selected_source_rows()
        if not rows:
            return
        it = self.state.items[rows[0]]
        self.load_preview(it.input_path)
        self.update_why_panel(it)

    def load_preview(self, path: Path):
        try:
            if self.preview:
                self.preview.close()
            self.preview = PdfPreview(path)
            self.preview_page = 0
            self.page_spin.setMaximum(max(1, self.preview.page_count))
            self.page_spin.setValue(1)
            self.zoom_slider.setValue(100)
            self.preview_zoom = 1.0
            self.load_thumbs()
            self.render_preview()
        except Exception as e:
            self.preview_label.setText(f"Preview error: {e}")

    def load_thumbs(self):
        self.thumb_list.clear()
        if not self.preview:
            return
        thumbs = self.preview.render_thumbnails(zoom=0.2, max_pages=30)
        for i, img in enumerate(thumbs):
            pix = QPixmap.fromImage(img).scaledToWidth(180, Qt.SmoothTransformation)
            it = QListWidgetItem(f"{i+1}")
            it.setIcon(pix)
            self.thumb_list.addItem(it)

    def on_thumb_clicked(self, item: QListWidgetItem):
        idx = self.thumb_list.row(item)
        self.set_page(idx)

    def on_page_spin(self, v: int):
        self.set_page(v - 1)

    def on_zoom(self, v: int):
        self.preview_zoom = max(0.25, min(3.0, v / 100.0))
        self.render_preview()

    def set_page(self, page_index: int):
        if not self.preview:
            return
        self.preview_page = max(0, min(self.preview.page_count - 1, page_index))
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(self.preview_page + 1)
        self.page_spin.blockSignals(False)
        self.render_preview()

    def render_preview(self):
        if not self.preview:
            return
        img = self.preview.render_page(self.preview_page, zoom=self.preview_zoom)
        pix = QPixmap.fromImage(img)

        if self.sensitive_mode:
            # cheap "blur": scale down/up (good enough)
            small = pix.scaled(
                pix.width() // 2,
                pix.height() // 2,
                Qt.KeepAspectRatio,
                Qt.FastTransformation,
            )
            pix = small.scaled(
                pix.width(), pix.height(), Qt.KeepAspectRatio, Qt.FastTransformation
            )

        self.preview_label.setPixmap(
            pix.scaled(
                self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

    def update_why_panel(self, it):
        ev = "<br>".join([f"• {e}" for e in (it.evidence or [])]) or "(none)"
        txt = f"""
        <b>Sender</b>: {it.sender or "(empty)"}<br>
        <b>Confidence</b>: final {it.conf_final:.2f} | stage1 {it.conf_stage1:.2f} | stage2 {it.conf_stage2:.2f} | used stage {it.stage_used}<br>
        <b>Extraction</b>: {it.extraction_method} (pages: {it.pages_processed})<br>
        <b>DocType</b>: {it.document_type}<br>
        <b>Filename label</b>: {it.filename_label}<br>
        <b>Target folder</b>: {it.effective_folder() or it.target_folder}<br>
        <b>Mapping match</b>: {it.mapping_match_type} {it.mapping_match_value}<br>
        <b>LLM target_folder</b>: {it.llm_target_folder or "(none)"} | <b>is_private</b>: {str(it.llm_is_private)}<br>
        <b>Folder reason</b>: {it.llm_folder_reason or "(none)"}<br>
        <b>Evidence</b>:<br>{ev}<br>
        <b>Notes</b>: {it.notes or "(none)"}<br>
        """
        self.llm_text.setHtml(txt)


def run_gui(cfg, mapper, client, logger):
    app = QApplication([])
    w = MainWindow(cfg, mapper, client, logger)
    w.show()
    app.exec()
