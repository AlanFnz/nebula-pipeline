from rich.console import Console
from rich.text import Text
import pyfiglet

_console = Console()

_AMBER = "color(214)"
_DIM   = "dim white"


def _pad_block(block: str, width: int) -> str:
    """left-pad each line of a figlet block to a fixed width"""
    return "\n".join(line.ljust(width) for line in block.rstrip("\n").splitlines())


def get_banner_text() -> Text:
    title = pyfiglet.figlet_format("afnz", font="ansi_shadow")
    width = max(len(line) for line in title.splitlines())

    sub1 = pyfiglet.figlet_format("analog", font="future")
    sub2 = pyfiglet.figlet_format("degradation", font="future")

    t = Text()
    t.append(title, style=f"bold {_AMBER}")
    t.append("\n")
    t.append(_pad_block(sub1, width) + "\n", style=_AMBER)
    t.append(_pad_block(sub2, width) + "\n\n", style=_AMBER)
    return t


def print_banner() -> None:
    _console.print(get_banner_text())
