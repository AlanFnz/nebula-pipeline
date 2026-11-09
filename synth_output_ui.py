"""Read-only monitor and export descriptions, independent of render settings."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMenu, QToolButton, QVBoxLayout, QWidget, QWidgetAction


PREVIEW_HINT = ('Preview resolution limits the longest edge to 360 or 720 pixels, '
                'without enlarging smaller canvases. Full canvas uses the output dimensions. '
                'View zoom only changes display size. Export always renders the full canvas.')


def cache_caption(scope, ready, total):
    state = 'complete' if total and ready == total else 'partial' if ready else 'not prepared'
    return f'{scope}: {ready}/{total} frames · {state}'


def preparation_caption(scope, ready, total, range_ready=False):
    if total and ready == total:
        return f'{scope} fully prepared · press Play'
    if range_ready:
        return 'Preview partially prepared · prepared range ready'
    return 'Preview partially prepared' if ready else 'Preview not prepared'


def export_audio_label(document, *, montage=False):
    """Describe the applied route used by synth_media / export_montage."""
    track = document.get('soundtrack')
    if montage:
        route = 'soundtrack' if track and track['export_audio'] == 'soundtrack' else 'silent'
    else:
        from synth_visual_sound import audio_output
        route = audio_output(document)
    if route == 'generated':
        return 'Generated sound · applied settings'
    if route == 'soundtrack':
        return f"Soundtrack · {Path(track['path']).name}"
    from synth_live_mode import is_live
    if not montage and is_live(document.get('generated_sound')):
        return 'Silent · Live audio is external; import its recording as a soundtrack'
    if route == 'footage' and document.get('footage'):
        from synth_section_sources import rendered_footage
        if any(source['audio'] == 'keep' and source['has_audio'] for source in rendered_footage(document)):
            return 'Original footage audio · kept clips'
    return 'Silent · no audio track'


def export_rows(document, *, preset=None, montage=False):
    data = document if document is not None else preset
    canvas = data.get('canvas', preset or data)
    fps = data['fps'] if document is not None else data['export_fps']
    frames = sum(c['frames'] for c in data['clips']) if montage else max(1, round(
        (data['duration'] if document is not None else data['loop_seconds']) * fps))
    width, height = canvas['width'], canvas['height']
    rows = [('Export', data.get('name', 'Untitled')),
            ('Range', 'Entire montage' if montage else 'Entire composition' if document is not None else 'Entire loop'),
            ('Canvas', f'{width} × {height} px'),
            ('Timing', f'{fps} FPS · {frames / fps:.3f} s · {frames} frames'),
            ('Audio', export_audio_label(data if document is not None else {}, montage=montage))]
    from synth_live_mode import is_live
    if not montage and is_live(data.get('generated_sound')):
        rows.append(('Live playback', 'MIDI only. Record or export audio in Live, then import it as a soundtrack to include it in the MP4.'))
    if width % 2 or height % 2:
        rows.append(('MP4 size', f'{width + width % 2} × {height + height % 2} px · padded to even dimensions'))
    rows.append(('Format', 'MP4 · H.264'))
    if montage:
        rows.append(('Audio scope', 'Uses the montage soundtrack setting; block audio is not mixed.'))
    rows.append(('Preview', 'Zoom, preview resolution and prepared frames do not change export size. Every output frame is rendered.'))
    return rows


class ExportSummaryButton(QToolButton):
    """Optional disclosure next to Export; opening it never applies a draft."""
    def __init__(self, parent, provider, export_button):
        super().__init__(parent)
        self.provider, self.export_button = provider, export_button
        self.setText('Details'); self.setAccessibleName('Export summary')
        self.setToolTip('Export summary — document, output size, timing and applied audio.')
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setProperty('secondaryAction', True)
        menu = QMenu(self); self.setMenu(menu)
        card = QWidget(); card.setFixedWidth(370)
        layout = QVBoxLayout(card); layout.setContentsMargins(14, 10, 14, 10); layout.setSpacing(7)
        self.summary_text = QLabel(); self.summary_text.setTextFormat(Qt.TextFormat.PlainText)
        self.summary_text.setWordWrap(True); self.summary_text.setAccessibleName('Export details')
        layout.addWidget(self.summary_text)
        action = QWidgetAction(menu); action.setDefaultWidget(card); menu.addAction(action)
        menu.addSeparator()
        self.export_action = menu.addAction('Export MP4…', export_button.click)
        menu.aboutToShow.connect(self.refresh_summary)

    def refresh_summary(self):
        self.rows = self.provider()
        self.summary_text.setText('\n\n'.join(f'{name}\n{value}' for name, value in self.rows))
        self.export_action.setEnabled(self.export_button.isEnabled())
