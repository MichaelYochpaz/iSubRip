from collections.abc import Iterator
from contextlib import contextmanager
import sys
from typing import Any

from rich.console import Console
from rich.live import Live


def _configure_windows_console_output() -> None:
    """Use UTF-8 for multilingual CLI output on Windows."""
    encoding = (sys.stdout.encoding or "").lower().replace("-", "")
    if sys.platform != "win32" or encoding in {"utf8", "cp65001"}:
        return

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


_configure_windows_console_output()

console = Console(
    highlight=False,
)

@contextmanager 
def conditional_live(renderable: Any) -> Iterator[Live | None]:
    """
    A context manager that conditionally enables Rich's Live display based on console interactivity.
    
    When console.is_interactive is True, this behaves like Rich's Live display.
    When console.is_interactive is False, live updates are disabled.

    Args:
        renderable: The Rich renderable object to display in live mode.

    Yields:
        Optional[Live]: The Live display object if console is interactive, None otherwise.

    Example:
        ```python
        with conditional_live(progress) as live:
            # Your code here
            if live:  # Optional: Check if live display is active
                live.update(...)
        ```
    """
    if console.is_interactive:
        with Live(renderable, console=console) as live:
            yield live
    else:
        yield None
