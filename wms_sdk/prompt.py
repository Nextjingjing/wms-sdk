"""Checkbox menu for the command line: arrow keys move, space selects, Enter
confirms. Standard library only (msvcrt on Windows, termios elsewhere).
"""

import os
import sys
from collections.abc import Callable
from typing import TextIO

# Keys read_key() returns.
UP, DOWN, SPACE, ENTER, OTHER = "up", "down", "space", "enter", "other"


def checkbox(
    title: str,
    items: list[tuple[str, str]],
    *,
    selected: set[str] = frozenset(),
    read_key: Callable[[], str] | None = None,
    out: TextIO | None = None,
) -> list[str]:
    """Let the user tick items; returns the ticked values in `items` order.

    `items` are (value, description); `selected` are ticked at the start.
    Ctrl+C raises KeyboardInterrupt and Ctrl+D / Ctrl+Z raise EOFError, so
    the caller can cancel cleanly.
    """
    read_key = read_key or _read_key
    out = out or sys.stdout
    _enable_ansi()
    width = max(len(value) for value, _ in items)
    cursor, ticked = 0, set(selected)

    def draw(first: bool) -> None:
        if not first:
            out.write(f"\x1b[{len(items)}A")  # back to the first item
        for index, (value, description) in enumerate(items):
            pointer = ">" if index == cursor else " "
            mark = "x" if value in ticked else " "
            out.write(f"\r\x1b[2K{pointer} [{mark}] {value.ljust(width)}  {description}\n")
        out.flush()

    # ASCII only: a Windows console on a legacy code page (e.g. cp874) cannot print arrows.
    out.write(f"{title} (up/down move, space select, Enter confirm)\n")
    draw(first=True)
    while True:
        key = read_key()
        if key == ENTER:
            return [value for value, _ in items if value in ticked]
        if key == UP:
            cursor = (cursor - 1) % len(items)
        elif key == DOWN:
            cursor = (cursor + 1) % len(items)
        elif key == SPACE:
            ticked ^= {items[cursor][0]}
        draw(first=False)


def _enable_ansi() -> None:
    if os.name == "nt":
        # An empty command turns on ANSI escape handling in the Windows console.
        os.system("")


def _read_key() -> str:
    if os.name == "nt":
        import msvcrt

        char = msvcrt.getwch()
        if char in ("\x00", "\xe0"):  # arrow keys come as a prefix + code
            return {"H": UP, "P": DOWN}.get(msvcrt.getwch(), OTHER)
        return _plain(char)

    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        char = sys.stdin.read(1)
        if char == "\x1b":
            if sys.stdin.read(1) == "[":
                return {"A": UP, "B": DOWN}.get(sys.stdin.read(1), OTHER)
            return OTHER
        return _plain(char)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def _plain(char: str) -> str:
    if char == "\x03":
        raise KeyboardInterrupt
    if char in ("\x04", "\x1a"):
        raise EOFError
    return {" ": SPACE, "\r": ENTER, "\n": ENTER, "k": UP, "j": DOWN}.get(char, OTHER)
