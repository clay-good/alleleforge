"""Which of a command's flags take a string, and which take a path.

Read from the annotations on the command's own function, because those are the one
description of a flag that typer does not own. Asking the parsed parameter instead
(`isinstance(p.type, StringParamType)`) broke when typer 0.29 removed both that class and
`p.type`, and it stopped the whole suite at collection.
"""

from __future__ import annotations

import types
import typing
from pathlib import Path
from typing import Any


def _value_type(annotation: Any) -> Any:
    """Return the type of one value: `str` for `str | None` and for `list[str] | None`."""
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        present = [a for a in typing.get_args(annotation) if a is not type(None)]
        return _value_type(present[0]) if len(present) == 1 else annotation
    if origin is list:
        return _value_type(typing.get_args(annotation)[0])
    return annotation


def _flags_of_type(command: Any, value_type: type) -> list[str]:
    hints = typing.get_type_hints(command.callback)
    return [
        p.opts[0]
        for p in command.params
        if p.opts and p.opts[0].startswith("-") and _value_type(hints[p.name]) is value_type
    ]


def string_flags(command: Any) -> list[str]:
    """Every flag of `command` whose value is a string."""
    return _flags_of_type(command, str)


def path_flags(command: Any) -> list[str]:
    """Every flag of `command` whose value is a path."""
    return _flags_of_type(command, Path)
