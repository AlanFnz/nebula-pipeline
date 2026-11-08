"""Document navigation inside one native window.

The montage owns the document. A block editor is a temporary editing context;
return, Save and Export validate and commit it into that document. Neither
navigation nor display quality changes the render recipe or montage clocks.
"""
from __future__ import annotations

import copy

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QStackedWidget, QWidget


class WorkspaceNavigation(QObject):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.active = host
        self.montage = None
        self.editor = None
        self.clip_id = None
        self.original_project = None
        self.disposing = False
        self.presented_menus = []
        self.menus = {host: list(host.menuBar().actions())}
        self.home = host.takeCentralWidget()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.home)
        host.setCentralWidget(self.stack)
        host.workspace_navigation = self

    def add_view(self, view):
        view.workspace_navigation = self
        if view.parentWidget() is not self.stack:
            view.setParent(self.stack, Qt.WindowType.Widget)
        view.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        view.menuBar().setNativeMenuBar(False)
        view.menuBar().hide()
        self.menus[view] = list(view.menuBar().actions())
        # Cocoa permits a menu in only one menu bar. Detach it from the hidden
        # embedded view before exposing it in the native window's bar.
        for action in self.menus[view]: view.menuBar().removeAction(action)
        self.stack.addWidget(view)
        view.windowTitleChanged.connect(lambda _title: self.update_title())

    def activate(self, view):
        previous = self.active
        previous.preview_suspended = True
        if hasattr(previous, 'cancel_preparation'):
            previous.play.setChecked(False)
            previous.cancel_video_import()
            if previous.study_job: previous.study_job.cancel.cancel()
            previous.cancel_preparation()
            previous.cancel_foreground_render()
            previous.preview_debounce.stop()
        else:
            previous.stop()
            if previous.prepare_task: previous.prepare_task.cancel.cancel()
            if previous.preview_task: previous.preview_task.cancel.cancel()
        self.active = view
        bar = self.host.menuBar()
        for menu in self.presented_menus:
            menu.setEnabled(False)
            bar.removeAction(menu.menuAction())
            menu.deleteLater()
        self.presented_menus = []
        for actions in self.menus.values():
            for action in actions:
                bar.removeAction(action)
                action.setEnabled(False)
        for action in self.menus[view]:
            action.setEnabled(True)
            # Keep native menus owned by the actual window, not the hidden
            # QMainWindow embedded in it. Share actions so enabled states,
            # shortcuts and callbacks remain those of the visible editor.
            menu = QMenu(action.text(), bar)
            menu.addActions(action.menu().actions())
            bar.addMenu(menu)
            self.presented_menus.append(menu)
        self.stack.setCurrentWidget(self.home if view is self.host else view)
        view.preview_suspended = False
        self.update_title()
        if hasattr(view, 'refresh_cache_status'): view.refresh_cache_status()
        view.request_frame()
        if hasattr(view, 'schedule_auto_preparation'): view.schedule_auto_preparation()

    def update_title(self):
        if self.montage is None: return
        dirty = self.montage.document != self.montage.clean
        if self.editor:
            dirty = dirty or self.editor.has_unsaved_changes()
        name = self.montage.document['name']
        if self.editor:
            clip = next(c for c in self.montage.document['clips'] if c['id'] == self.clip_id)
            name += ' › ' + clip['name']
        title = f"Nebula · {name}{' *' if dirty else ''}"
        if self.host.windowTitle() != title: self.host.setWindowTitle(title)
        if self.editor: self.editor.refresh_sound_context()

    def show_montage(self, document, path=None):
        from synth_montage_ui import MontageWindow
        montage = MontageWindow(document, path=path, parent=self.stack, embedded=True)
        self.montage = montage
        self.add_view(montage)
        if hasattr(self.host, 'quality'): montage.detail.setCurrentIndex(self.host.quality.currentIndex())
        self.activate(montage)
        return montage

    def edit_clip(self, montage, key):
        from synth_composition import section_placements
        from synth_montage import clip_project
        from synth_studio import SynthStudio
        if self.editor is not None: return self.editor
        clip = next(c for c in montage.document['clips'] if c['id'] == key)
        project = clip_project(montage.document, clip)
        montage.stop()
        self.montage = montage
        montage.select_clip(key)
        editor = SynthStudio(composition=project, parent=self.stack, embedded=True)
        self.editor, self.clip_id = editor, key
        self.original_project = copy.deepcopy(editor.composition)
        montage.editors.append(editor)
        self.add_view(editor)
        # File commands act on the complete project; the inspector acts on the block.
        for control in (editor.new_piece_button, editor.import_video_button,
                        editor.montage_button, editor.open_button, editor.study_controls):
            control.hide()
        for action in (editor.new_piece_action, editor.montage_action):
            action.setVisible(False)
        editor.save_study_button.setVisible(False)
        editor.quality.setCurrentIndex(montage.detail.currentIndex())
        editor.save_button.setAccessibleName('Save montage')
        editor.save_button.setToolTip('Save the complete montage, including this block.')
        editor.export_button.setText('Export montage')
        editor.document_title.setText(clip['name'])
        bar = QWidget()
        row = QHBoxLayout(bar); row.setContentsMargins(0, 0, 0, 4)
        editor.back_to_montage = QPushButton('← Back to montage')
        editor.back_to_montage.setToolTip('Return to the montage with your changes. You can undo them there.')
        editor.back_to_montage.clicked.connect(self.return_to_montage)
        row.addWidget(editor.back_to_montage)
        breadcrumb = QLabel(f"{montage.document['name']}  ›  {clip['name']}")
        breadcrumb.setWordWrap(True); row.addWidget(breadcrumb, 1)
        editor.header_host.layout().insertWidget(0, bar)
        back = QAction('Back to montage', editor)
        back.setShortcut(QKeySequence('Ctrl+[')); back.triggered.connect(self.return_to_montage)
        self.menus[editor][0].menu().addAction(back)
        index = next((i for i, a, b, _ in section_placements(project)
                      if a <= clip['in_frame'] / montage.document['fps'] < b), 0)
        editor.composer.select_section(index)
        editor.timeline.setValue(round(clip['in_frame'] / montage.document['fps'] * project['fps']))
        self.activate(editor)
        return editor

    def commit_editor(self, purpose='leaving this block', *, leaving=True):
        editor = self.editor
        if editor is None: return True
        if not editor.resolve_sound_draft(purpose, leaving=leaving): return False
        if editor.audition_pending():
            editor.status.setText('Keep or discard the temporary variation before returning or saving.')
            return False
        editor.finish_focused_edit()
        if not editor.prepare_document_save(): return False
        if editor.composition is None:
            editor.status.setText('Keep this block as a composition.'); return False
        if editor.composition != self.original_project:
            doc = copy.deepcopy(self.montage.document)
            clip = next(c for c in doc['clips'] if c['id'] == self.clip_id)
            clip['document'] = copy.deepcopy(editor.composition)
            try:
                self.montage.commit(doc)
            except (ValueError, OSError) as error:
                editor.status.setText(f'Could not update this block: {error}')
                return False
            self.original_project = copy.deepcopy(editor.composition)
        editor.mark_document_clean()
        self.update_title()
        return True

    def return_to_montage(self):
        if not self.commit_editor(): return False
        editor = self.editor
        self.editor = None
        if editor is not None: self.montage.detail.setCurrentIndex(editor.quality.currentIndex())
        self.activate(self.montage)
        if editor is not None:
            self.dispose(editor)
            self.montage.editors.remove(editor)
        self.montage.status.setText('Back in the montage. Your block edits are kept; Save stores the complete project.')
        return True

    def save(self, save_as=False):
        if not self.commit_editor('saving', leaving=False): return False
        saved = self.montage.save(save_as)
        self.update_title()
        if saved and self.editor: self.editor.status.setText('Montage saved, including this block.')
        return saved

    def export(self):
        if not self.return_to_montage(): return
        self.montage.export_dialog()

    def can_leave(self):
        if self.montage is None: return True
        if self.montage.export_task:
            self.active.status.setText('Cancel the export before closing or opening another project.')
            return False
        if not self.commit_editor(): return False
        return self.montage.may_replace()

    def dispose(self, view):
        self.disposing = True
        try:
            view.close()
        finally:
            self.disposing = False
        self.stack.removeWidget(view)
        self.menus.pop(view, None)
        view.deleteLater()

    def leave_montage(self):
        """Called only after can_leave succeeds; no second save prompt."""
        if self.editor:
            editor = self.editor; self.editor = None
            self.montage.editors.remove(editor)
            self.dispose(editor)
        montage = self.montage
        self.montage = None
        self.activate(self.host)
        if montage is not self.host: self.dispose(montage)
        self.host.update_document_title()

    def shutdown(self):
        if self.editor:
            editor = self.editor; self.editor = None
            self.montage.editors.remove(editor)
            self.dispose(editor)
        if self.montage and self.montage is not self.host:
            self.dispose(self.montage)
        self.montage = None
