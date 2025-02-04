from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Optional

from rich.console import Console
from rich.live import Live

console = Console(
    highlight=False,
)

@contextmanager 
def conditional_live(renderable: Any) -> Iterator[Optional[Live]]:
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
