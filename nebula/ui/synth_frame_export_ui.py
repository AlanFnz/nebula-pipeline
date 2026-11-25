"""Single-frame navigation and the still-image save dialog."""
from pathlib import Path

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, QThreadPool, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QAbstractSpinBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QMenu, QToolButton, QVBoxLayout, QWidget)

from nebula.core.synth_canvas import preview_size
from nebula.ui.studio_task import Task
from nebula.ui.studio_theme import terminal_font
from nebula.ui.studio_widgets import ComboBox, SpinBox


def frame_timecode(frame, fps):
    minutes, cents = divmod(round(frame * 100 / fps), 6000)
    return f'{minutes:02d}:{cents // 100:02d}.{cents % 100:02d}'


class PlayheadFrame(SpinBox):
    def __init__(self, slider, pause):
        super().__init__()
        self.slider, self.pause = slider, pause
        self.setPrefix('Frame ')
        self.setFont(terminal_font())
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setKeyboardTracking(False)
        self.setAccessibleName('Playhead frame')
        self.setToolTip('Frame 0 is the start. Type a frame number and press Enter to seek.')
        self.valueChanged.connect(slider.setValue)

    def sync(self):
        with QSignalBlocker(self):
            self.setRange(self.slider.minimum(), self.slider.maximum())
            self.setValue(self.slider.value())

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if event.reason() in (Qt.FocusReason.MouseFocusReason, Qt.FocusReason.TabFocusReason,
                              Qt.FocusReason.BacktabFocusReason):
            self.pause()
            # A click places the text cursor after the focus event.
            if event.reason() == Qt.FocusReason.MouseFocusReason:
                QTimer.singleShot(0, self, self.selectAll)
            else:
                self.selectAll()

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.slider.setFocus(Qt.FocusReason.OtherFocusReason)


class ExportButton(QToolButton):
    def __init__(self, movie, still):
        super().__init__()
        self.setObjectName('primary')
        self.setText('Export MP4')
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.clicked.connect(movie)
        menu = QMenu(self)
        self.frame_action = menu.addAction('Export frame…', still)
        self.setMenu(menu)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange and hasattr(self, 'frame_action'):
            self.frame_action.setEnabled(self.isEnabled())


class FrameExportDialog(QFileDialog):
    PNG = 'PNG image (*.png)'
    JPEG = 'JPEG image (*.jpg *.jpeg)'

    def __init__(self, parent, suggested_path, canvas, frame, fps, scope, render):
        super().__init__(parent)
        self.setOption(QFileDialog.Option.DontUseNativeDialog)
        self.setStyleSheet('QFileDialog QToolButton { padding: 2px; }')
        self.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        self.setFileMode(QFileDialog.FileMode.AnyFile)
        self.setWindowTitle('Export frame')
        self.setLabelText(QFileDialog.DialogLabel.FileType, 'Format')
        self.setNameFilters([self.PNG, self.JPEG])
        self.setDefaultSuffix('png')
        path = Path(suggested_path)
        self.setDirectory(str(path.parent))
        self.selectFile(f'{path.stem}-f{frame:06d}.png')

        controls = QWidget()
        row = QHBoxLayout(controls)
        row.setContentsMargins(0, 4, 0, 0)
        self.thumbnail = QLabel('Rendering…')
        self.thumbnail.setFixedSize(90, 72)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setAccessibleName('Selected frame thumbnail')
        row.addWidget(self.thumbnail)
        info = QVBoxLayout()
        row.addLayout(info)
        info.addWidget(QLabel(f'{scope} · Frame {frame} · {frame_timecode(frame, fps)}'))
        settings = QHBoxLayout()
        info.addLayout(settings)
        label = QLabel('Resolution')
        self.resolution = ComboBox()
        self.resolution.setAccessibleName('Frame export resolution')
        label.setBuddy(self.resolution)
        settings.addWidget(label)
        settings.addWidget(self.resolution)
        for title, edge in (('360 px', 360), ('720 px', 720), ('Full canvas', None)):
            width, height = preview_size(canvas, edge)
            self.resolution.addItem(f'{title} · {width} × {height} px', (width, height))
        self.resolution.setCurrentIndex(2)
        self.quality_label = QLabel('JPEG quality')
        self.quality = SpinBox()
        self.quality.setRange(1, 100)
        self.quality.setValue(95)
        self.quality.setAccessibleName('JPEG quality')
        self.quality_label.setBuddy(self.quality)
        settings.addWidget(self.quality_label)
        settings.addWidget(self.quality)
        settings.addStretch()
        row.addStretch()
        grid = self.layout()
        grid.addWidget(controls, grid.rowCount(), 0, 1, grid.columnCount())
        # The widget-based file dialog updates this combo for keyboard and mouse
        # selection; its native filterSelected notification is platform dependent.
        self.findChild(QComboBox, 'fileTypeCombo').currentTextChanged.connect(self.update_format)
        self.update_format(self.PNG)

        size = preview_size(canvas, 180)
        self.preview_job = Task(lambda cancel, _progress: render(size, cancel))
        self.preview_job.signals.done.connect(self.show_thumbnail)
        self.preview_job.signals.failed.connect(self.thumbnail_failed)
        self.finished.connect(self.preview_job.cancel.cancel)
        QThreadPool.globalInstance().start(self.preview_job)

    def show_thumbnail(self, image):
        pixmap = QPixmap.fromImage(image.toqimage())
        self.thumbnail.setPixmap(pixmap.scaled(self.thumbnail.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))

    def thumbnail_failed(self, reason):
        self.thumbnail.setText('Unavailable')
        self.thumbnail.setToolTip(reason)

    def update_format(self, name_filter):
        jpeg = name_filter == self.JPEG
        self.setDefaultSuffix('jpg' if jpeg else 'png')
        self.quality_label.setVisible(jpeg)
        self.quality.setVisible(jpeg)

    def accept(self):
        # QFileDialog checks for overwrites on the final filename.
        paths = self.selectedFiles()
        if paths:
            path = Path(paths[0])
            suffixes = ('.jpg', '.jpeg') if self.selectedNameFilter() == self.JPEG else ('.png',)
            if not path.is_dir() and path.suffix.lower() not in suffixes:
                suffix = path.suffix if path.suffix.lower() not in ('.jpg', '.jpeg', '.png') else ''
                # Qt preserves an in-focus filename edit when selectFile is called.
                self.resolution.setFocus(Qt.FocusReason.OtherFocusReason)
                self.selectFile(str(path.with_suffix(suffix + suffixes[0])))
        super().accept()

    @classmethod
    def choose(cls, parent, suggested_path, canvas, frame, fps, scope, render):
        dialog = cls(parent, suggested_path, canvas, frame, fps, scope, render)
        try:
            if dialog.exec() == QFileDialog.DialogCode.Accepted:
                return Path(dialog.selectedFiles()[0]), dialog.resolution.currentData(), dialog.quality.value()
        finally:
            dialog.preview_job.cancel.cancel()
            dialog.deleteLater()
