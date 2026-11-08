"""Install only Nebula's companion into an explicitly chosen Live User Library."""
from pathlib import Path
import argparse
import shutil


def install(library):
    library = Path(library).expanduser().resolve()
    if not library.is_dir():
        raise ValueError('Choose an existing Ableton User Library directory.')
    source = Path(__file__).resolve().parents[1] / 'integrations/ableton/Nebula_Visuals'
    target = library / 'Remote Scripts/Nebula_Visuals'
    target.mkdir(parents=True, exist_ok=True)
    for name in ('__init__.py', 'surface.py', 'watch.py'):
        shutil.copy2(source / name, target / name)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('user_library', type=Path)
    args = parser.parse_args()
    print(install(args.user_library))
    print('Restart Live. MIDI control surface: Nebula_Visuals; Input: None; Output: Nebula Control.')
