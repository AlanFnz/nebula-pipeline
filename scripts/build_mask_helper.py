"""Compile the optional, offline macOS foreground-mask helper."""
from pathlib import Path
import subprocess
import platform

ROOT = Path(__file__).resolve().parents[1]


def build_mask_helper():
    output = ROOT / 'build/native/nebula-mask'
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['swiftc', '-O', '-target', f'{platform.machine()}-apple-macosx14.0',
                    str(ROOT / 'native/nebula-mask.swift'), '-o', str(output)], check=True)
    return output


if __name__ == '__main__': print(build_mask_helper())
