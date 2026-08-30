from __future__ import annotations

from io import TextIOWrapper
import sys
from unittest.mock import Mock

from isubrip.cli import _configure_windows_console_output


def test_configure_windows_console_output_uses_utf8(monkeypatch) -> None:
    stdout = Mock(spec=TextIOWrapper)
    stdout.encoding = "cp1255"
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "platform", "win32")

    _configure_windows_console_output()

    stdout.reconfigure.assert_called_once_with(encoding="utf-8")


def test_configure_windows_console_output_keeps_utf8(monkeypatch) -> None:
    stdout = Mock(spec=TextIOWrapper)
    stdout.encoding = "cp65001"
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "platform", "win32")

    _configure_windows_console_output()

    stdout.reconfigure.assert_not_called()


def test_configure_windows_console_output_does_not_change_other_platforms(monkeypatch) -> None:
    stdout = Mock(spec=TextIOWrapper)
    stdout.encoding = "cp1255"
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "platform", "linux")

    _configure_windows_console_output()

    stdout.reconfigure.assert_not_called()
