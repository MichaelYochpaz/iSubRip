from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rich.progress import TimeElapsedColumn
from rich.text import Text

if TYPE_CHECKING:
    from rich.progress import Task


class MinsAndSecsTimeElapsedColumn(TimeElapsedColumn):
    """Renders time elapsed in minutes and seconds."""

    def render(self, task: Task) -> Text:
        """Show time elapsed."""
        elapsed = task.finished_time if task.finished else task.elapsed

        if elapsed is None:
            return Text("-:--", style="progress.elapsed")

        minutes, seconds = divmod(math.ceil(elapsed), 60)

        return Text(f"{minutes:02d}:{seconds:02d}", style="progress.elapsed")
