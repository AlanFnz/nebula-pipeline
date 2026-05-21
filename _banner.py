from rich.console import Console
from rich.text import Text
import pyfiglet

_console = Console()

_AMBER    = "color(214)"
_SUBTITLE = "color(172)"


def get_banner_text() -> Text:
    title = pyfiglet.figlet_format("afnz", font="ansi_shadow", width=500)
    sub   = pyfiglet.figlet_format("analog degradation", font="smblock", width=500)

    t = Text()
    title_lines = "\n".join(l for l in title.split("\n") if l.strip())
    t.append(title_lines, style=f"bold {_AMBER}")
    t.append("\n")
    t.append(sub.strip("\n") + "\n", style=_SUBTITLE)
    return t


def print_banner() -> None:
    _console.print(get_banner_text())
