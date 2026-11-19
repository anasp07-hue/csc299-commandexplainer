"""ANSI colors for the output, and the rules for turning them off (SPEC.md §3.3.2, ADR 0020)."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

_RESET = "\033[0m"
_BOLD = "\033[1m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_MAGENTA = "\033[35m"
_CYAN = "\033[36m"
_ANSI_PATTERN = re.compile(r"\033\[[0-9;]*m")


def colors_enabled(
    isatty: Callable[[], bool], env: Mapping[str, str], no_color_flag: bool
) -> bool:
    """True only if output is a terminal, NO_COLOR isn't set, and --no-color wasn't given.

    NO_COLOR counts as set when it has any non-empty value (the no-color.org rule).
    """
    if no_color_flag or env.get("NO_COLOR", ""):
        return False
    try:
        return bool(isatty())
    except (AttributeError, OSError, ValueError):
        return False


def strip_colors(text: str) -> str:
    """Remove ANSI color codes, leaving the plain text."""
    return _ANSI_PATTERN.sub("", text)


@dataclass(frozen=True)
class Palette:
    """Wraps text in color codes when enabled, and returns it unchanged when not.

    Each method names what the color is for, so callers don't pick colors directly:
    command names are bold, flags cyan, warnings red, "Did you mean" yellow, and
    operators magenta.
    """

    enabled: bool = False

    def _paint(self, code: str, text: str) -> str:
        """Wrap text in one color code, if colors are on and there's text to wrap."""
        return f"{code}{text}{_RESET}" if self.enabled and text else text

    def command(self, text: str) -> str:
        """A command name."""
        return self._paint(_BOLD, text)

    def flag(self, text: str) -> str:
        """A flag like -r."""
        return self._paint(_CYAN, text)

    def warning(self, text: str) -> str:
        """A '⚠ Careful:' warning line."""
        return self._paint(_RED, text)

    def suggestion(self, text: str) -> str:
        """A 'Did you mean ...?' question."""
        return self._paint(_YELLOW, text)

    def operator(self, text: str) -> str:
        """An operator like | or >."""
        return self._paint(_MAGENTA, text)


PLAIN = Palette(enabled=False)
