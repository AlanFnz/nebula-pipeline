"""Stable font references; bundled indices keep their original rendering contract.

System fonts are referenced, never embedded. Core Text supplies the active macOS
catalog. A saved reference pins the file bytes, face and variation coordinates so
another installation cannot silently substitute a similarly named font.
"""
from functools import lru_cache
from pathlib import Path
import ctypes
import hashlib
import json
import math
import sys

from PIL import ImageFont

FONTS = ('Archivo Black', 'Anton / condensed', 'Space Mono Bold', 'Bodoni Moda / serif', 'Fraunces / soft serif', 'Fredoka / rounded')
FONT_FILES = ('ArchivoBlack-Regular.ttf', 'Anton-Regular.ttf', 'SpaceMono-Bold.ttf', 'BodoniModa.ttf', 'Fraunces.ttf', 'Fredoka.ttf')
FONT_ROOT = Path(__file__).parent / 'assets/fonts'


class FontUnavailable(ValueError):
    pass


def validate_font(value, maximum=5):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value) and int(value) == value and 0 <= value <= maximum:
            return int(value)
        raise ValueError('Invalid bundled typeface')
    if not isinstance(value, str) or len(value) > 16384:
        raise ValueError('Invalid system typeface reference')
    try:
        data = json.loads(value)
        if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1: raise ValueError()
        for key in ('path', 'postscript', 'family', 'style', 'sha256'):
            if not isinstance(data.get(key), str) or not data[key] or '\x00' in data[key]: raise ValueError()
        if not Path(data['path']).is_absolute(): raise ValueError()
        if len(data['sha256']) != 64 or any(c not in '0123456789abcdef' for c in data['sha256']): raise ValueError()
        if type(data.get('index')) is not int or not 0 <= data['index'] < 4096: raise ValueError()
        axes = data.get('axes')
        if not isinstance(axes, dict) or len(axes) > 32: raise ValueError()
        for tag, number in axes.items():
            if len(tag) != 4 or not tag.isascii() or isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number): raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise ValueError('Invalid system typeface reference') from None
    return value


def font_label(value, choices=FONTS):
    if isinstance(value, str):
        data = json.loads(validate_font(value))
        return f"{data['family']} · {data['style']}"
    return choices[int(value)]


def variable_weight(value):
    # System styles keep their selected native coordinates, unaffected by the
    # old study's bundled font-weight parameter.
    return isinstance(value, (int, float)) and value in (3, 4, 5)


def system_catalog():
    """Active font faces, without scanning folders or activating disabled fonts."""
    if sys.platform != 'darwin':
        return ()
    return _mac_catalog()


def _mac_catalog():
    cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    ct = ctypes.CDLL('/System/Library/Frameworks/CoreText.framework/CoreText')
    ptr, number = ctypes.c_void_p, ctypes.c_long
    signatures = (
        (ct, 'CTFontCollectionCreateFromAvailableFonts', [ptr], ptr),
        (ct, 'CTFontCollectionCreateMatchingFontDescriptors', [ptr], ptr),
        (ct, 'CTFontDescriptorCopyAttribute', [ptr, ptr], ptr),
        (cf, 'CFArrayGetCount', [ptr], number),
        (cf, 'CFArrayGetValueAtIndex', [ptr, number], ptr),
        (cf, 'CFStringGetLength', [ptr], number),
        (cf, 'CFStringGetMaximumSizeForEncoding', [number, ctypes.c_uint32], number),
        (cf, 'CFStringGetCString', [ptr, ptr, number, ctypes.c_uint32], ctypes.c_bool),
        (cf, 'CFURLCopyFileSystemPath', [ptr, ctypes.c_int], ptr),
        (cf, 'CFRelease', [ptr], None),
    )
    for lib, name, args, result in signatures:
        function = getattr(lib, name); function.argtypes = args; function.restype = result
    keys = {key: ptr.in_dll(ct, 'kCTFont'+key+'Attribute') for key in ('URL', 'Name', 'FamilyName', 'StyleName')}

    def string(ref):
        if not ref: return ''
        length = cf.CFStringGetMaximumSizeForEncoding(cf.CFStringGetLength(ref), 0x08000100) + 1
        buffer = ctypes.create_string_buffer(length)
        return buffer.value.decode('utf-8') if cf.CFStringGetCString(ref, buffer, length, 0x08000100) else ''

    collection = ct.CTFontCollectionCreateFromAvailableFonts(None)
    if not collection: return ()
    descriptors = None; rows = {}
    try:
        descriptors = ct.CTFontCollectionCreateMatchingFontDescriptors(collection)
        for i in range(cf.CFArrayGetCount(descriptors) if descriptors else 0):
            descriptor = cf.CFArrayGetValueAtIndex(descriptors, i)
            values = {}
            for key, attribute in keys.items():
                ref = ct.CTFontDescriptorCopyAttribute(descriptor, attribute)
                if not ref: continue
                try:
                    if key == 'URL':
                        path = cf.CFURLCopyFileSystemPath(ref, 0)
                        try: values[key] = string(path)
                        finally:
                            if path: cf.CFRelease(path)
                    else: values[key] = string(ref)
                finally: cf.CFRelease(ref)
            if not all(values.get(key) for key in ('URL', 'Name', 'FamilyName')): continue
            if values['FamilyName'].startswith('.'): continue  # Private UI fonts.
            row = dict(path=values['URL'], postscript=values['Name'], family=values['FamilyName'], style=values.get('StyleName') or 'Regular')
            rows[(row['postscript'], row['path'])] = row
    finally:
        if descriptors: cf.CFRelease(descriptors)
        cf.CFRelease(collection)
    return tuple(sorted(rows.values(), key=lambda row: (row['family'].casefold(), row['style'].casefold(), row['postscript'])))


def _stamp(path):
    stat = Path(path).stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


@lru_cache(maxsize=128)
def _digest(path, stamp):
    with open(path, 'rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


@lru_cache(maxsize=64)
def _faces(path, stamp):
    from fontTools.ttLib import TTFont, TTCollection, TTLibError
    with open(path, 'rb') as stream: collection = stream.read(4) == b'ttcf'
    try: owner = TTCollection(path, lazy=True) if collection else TTFont(path, lazy=True)
    except TTLibError as exc: raise ValueError('This font file format is not supported for rendering.') from exc
    fonts = owner.fonts if collection else [owner]
    faces = []
    try:
        for index, font in enumerate(fonts):
            names = font['name']
            family = names.getDebugName(16) or names.getDebugName(1) or ''
            style = names.getDebugName(17) or names.getDebugName(2) or 'Regular'
            axes = {a.axisTag: a.defaultValue for a in font['fvar'].axes} if 'fvar' in font else {}
            limits = {a.axisTag: (a.minValue, a.maxValue) for a in font['fvar'].axes} if 'fvar' in font else {}
            faces.append(dict(index=index, postscript=names.getDebugName(6) or '', family=family, style=style, axes=axes, limits=limits))
            if 'fvar' in font:
                for instance in font['fvar'].instances:
                    faces.append(dict(index=index, postscript=names.getDebugName(instance.postscriptNameID) or '' if instance.postscriptNameID != 65535 else '',
                                      family=family, style=names.getDebugName(instance.subfamilyNameID) or '', axes=dict(instance.coordinates), limits=limits))
    except TTLibError as exc:
        raise ValueError('This font file could not be read.') from exc
    finally: owner.close()
    return tuple(faces)


def reference_for_face(row):
    """Resolve the exact face in TTF/OTF/TTC, including named variable styles."""
    try:
        path = str(Path(row['path']).resolve()); stamp = _stamp(path)
        faces = _faces(path, stamp)
        face = next((f for f in faces if f['postscript'] == row['postscript']), None)
        if face is None:
            face = next((f for f in faces if f['family'].casefold() == row['family'].casefold() and f['style'].casefold() == row['style'].casefold()), None)
        if face is None: raise ValueError('This font style cannot be matched to its file.')
        data = dict(version=1, path=path, postscript=row['postscript'], family=row['family'], style=row['style'],
                    index=face['index'], axes=face['axes'], sha256=_digest(path, stamp))
        value = json.dumps(data, sort_keys=True, separators=(',', ':'))
        load_font(value, 48)
        return value
    except (OSError, ValueError, KeyError) as exc:
        raise FontUnavailable(f"Cannot use {row.get('family', 'this font')} · {row.get('style', '')}: {exc}") from exc


@lru_cache(maxsize=128)
def _parse(value):
    return json.loads(validate_font(value))


@lru_cache(maxsize=128)
def _relocated(value):
    data = _parse(value)
    for row in system_catalog():
        if row['postscript'] == data['postscript']:
            try:
                if _digest(row['path'], _stamp(row['path'])) == data['sha256']: return row['path']
            except OSError: pass
    return None


def resolve_font(value):
    data = _parse(value)
    def matches(path):
        if not path: return False
        try:
            return _digest(path, _stamp(path)) == data['sha256']
        except OSError: return False
    if matches(data['path']): return data['path']
    relocated = _relocated(value)
    if matches(relocated): return relocated
    raise FontUnavailable(f"Font unavailable: {font_label(value)}. Install the original font or choose a replacement in its Typeface control.")


def load_font(value, size, weight=400):
    if not isinstance(value, str):
        font = ImageFont.truetype(str(FONT_ROOT / FONT_FILES[int(value)]), size)
        if value == 3 and weight != 400: font.set_variation_by_axes([weight, 11])
        if value == 4: font.set_variation_by_axes([24, weight, 100, 1])
        if value == 5: font.set_variation_by_axes([min(700, weight), 100])
        return font
    data = _parse(value); path = resolve_font(value)
    try:
        font = ImageFont.truetype(path, size, index=data['index'])
        if data['axes']:
            faces = _faces(path, _stamp(path))
            base = next(f for f in faces if f['index'] == data['index'])
            if set(data['axes']) != set(base['axes']): raise ValueError('Font variation axes do not match the saved face')
            if any(not base['limits'][tag][0] <= number <= base['limits'][tag][1] for tag, number in data['axes'].items()):
                raise ValueError('Font variation is outside this style’s supported range')
            font.set_variation_by_axes([data['axes'][tag] for tag in base['axes']])
        return font
    except (OSError, ValueError, StopIteration) as exc:
        raise FontUnavailable(f'Cannot render {font_label(value)}: {exc}') from exc


def clear_font_catalog():
    _relocated.cache_clear()

