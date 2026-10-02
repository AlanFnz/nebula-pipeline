"""Fresh material is visible, editable and portable on common canvases."""
import copy

import numpy as np
import pytest

from synth_composition import compile_composition, load_composition, save_composition
from synth_effects import describe_effects
from synth_sequence import render_sequence_frame
from synth_starting_points import new_piece
from synth_subject import active_subjects, scope_states


@pytest.mark.parametrize('kind,options,subject', [
    ('text', {'text': 'MAKE SOMETHING'}, 'text'),
    ('shape', {'shape': 'rectangle'}, 'signal'),
    ('shape', {'shape': 'ellipse'}, 'signal'),
    ('shape', {'shape': 'circle'}, 'signal'),
    ('shape', {'shape': 'polygon'}, 'signal'),
    ('model', {'model': 'silhouette'}, 'silhouette'),
    ('model', {'model': 'particles'}, 'particles'),
])
@pytest.mark.parametrize('dimensions', [(1080, 1080), (1080, 1920), (1920, 1080)])
def test_visible_material_fits_canvas_and_survives_save_open(kind, options, subject, dimensions, tmp_path):
    width, height = dimensions
    canvas = dict(width=width, height=height, framing='preserve',
                  reference=dict(width=720, height=576, framing='native'))
    before = copy.deepcopy(canvas)
    piece = new_piece(kind, canvas, 12, **options)
    sequence = compile_composition(piece)
    assert canvas == before
    assert (sequence['canvas']['width'], sequence['canvas']['height']) == dimensions
    assert sequence['fps'] == 12 and sequence['duration'] == 6
    assert len(piece['sections']) == 1
    assert active_subjects(describe_effects(scope_states(piece))) == (subject,)
    size = (round(width * 192 / max(dimensions)), round(height * 192 / max(dimensions)))
    path = tmp_path / 'new-piece.json'
    save_composition(path, piece)
    reopened = compile_composition(load_composition(path))
    for time in (0., 5.5):
        image = render_sequence_frame(sequence, time, size)
        ys, xs = np.where(np.asarray(image).max(axis=2) > 80)
        assert len(xs) > 20, (kind, options, dimensions)
        # Clean starting material leaves space to see its entire outline.
        assert xs.min() > 0 and xs.max() < size[0] - 1
        assert ys.min() > 0 and ys.max() < size[1] - 1
        assert render_sequence_frame(reopened, time, size).tobytes() == image.tobytes()


@pytest.mark.parametrize('kind,options', [
    ('missing', {}), ('text', {'text': '  '}), ('text', {'text': 'x' * 513}),
    ('shape', {'shape': 'unknown'}), ('model', {'model': 'unknown'}),
])
def test_invalid_material_does_not_create_a_document(kind, options):
    with pytest.raises(ValueError): new_piece(kind, **options)
