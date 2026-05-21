from rich.console import Console
import pyfiglet

_console = Console()

# amber on dark — matches the pipeline's warm/cold palette
_AMBER = "color(214)"
_DIM   = "dim white"


def print_banner() -> None:
    art = pyfiglet.figlet_format("afnz", font="ansi_shadow")
    _console.print(f"[bold {_AMBER}]{art}[/]", end="")
    _console.print(f"  [{_DIM}]analog degradation pipeline[/]\n")
