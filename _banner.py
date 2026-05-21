from rich.console import Console
from rich.text import Text
import pyfiglet

_console = Console()

_AMBER = "color(214)"
_DIM   = "dim white"


def get_banner_text() -> Text:
    art = pyfiglet.figlet_format("afnz", font="ansi_shadow")
    t = Text()
    t.append(art, style=f"bold {_AMBER}")
    t.append("\n  analog degradation pipeline\n\n", style=_DIM)
    return t


def print_banner() -> None:
    _console.print(get_banner_text())
