"""Shared model importer for the object inspector and detailed editor."""
from pathlib import Path
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QFileDialog,QMessageBox,QApplication
from synth_mesh import decode_mesh,import_mesh,validate_mesh


class MeshControl(QWidget):
    changed=Signal(object)

    def __init__(self):
        super().__init__();self._value=''
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        row=QHBoxLayout();self.import_button=QPushButton('Import model…')
        self.import_button.setAccessibleName('Import 3D model')
        self.import_button.clicked.connect(self.import_file);row.addWidget(self.import_button)
        self.clear_button=QPushButton('Clear');self.clear_button.setAccessibleName('Clear 3D model')
        self.clear_button.clicked.connect(lambda:self.setValue(''));row.addWidget(self.clear_button);layout.addLayout(row)
        self.status=QLabel();self.status.setObjectName('muted');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.refresh()

    def value(self): return self._value

    def setValue(self,value):
        validate_mesh(value)
        if value==self._value:return
        self._value=value;self.refresh();self.changed.emit(value)

    def refresh(self):
        if self._value:
            _,_,f,name=decode_mesh(self._value)
            self.status.setText(f'{name} · {len(f):,} triangles · embedded in project')
            self.import_button.setText('Replace model…')
        else:
            self.status.setText('GLB / glTF · static geometry · Studio materials, including Black glass')
            self.import_button.setText('Import model…')
        self.clear_button.setEnabled(bool(self._value))

    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Import 3D model',str(Path.home()/'Downloads'),'3D models (*.glb *.gltf)')
        if not path:return
        error=None;QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:value=import_mesh(path)
        except ValueError as exc:error=str(exc)
        finally:QApplication.restoreOverrideCursor()
        if error:QMessageBox.warning(self,'Cannot import model',error)
        else:self.setValue(value)
