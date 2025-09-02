"""Very small subset of Typer's API used for the exercises.

This module implements enough functionality for the ``har2listings`` command
line interface to work in environments where the real ``typer`` dependency is
unavailable.  It supports registering subcommands via the ``@app.command``
decorator and parsing ``Option`` based arguments using :mod:`argparse`.
"""

from __future__ import annotations

import argparse
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List


@dataclass
class _OptionInfo:
    """Internal container describing an option."""

    default: Any
    flags: List[str]
    help: str = ""
    required: bool = False

    # Behave like the underlying default value when used directly in tests.
    def __getattr__(self, item: str) -> Any:  # pragma: no cover - delegation
        return getattr(self.default, item)

    def __str__(self) -> str:  # pragma: no cover - delegation
        return str(self.default)


def Option(default: Any, *flags: str, help: str = "") -> _OptionInfo:
    """Return an :class:`_OptionInfo` capturing CLI option metadata."""

    required = default is ...
    return _OptionInfo(default if not required else None, list(flags), help, required)


class Typer:
    """Lightweight replacement for :class:`typer.Typer`.

    Only implements the features required by this project: registering commands
    and parsing them from ``sys.argv`` using :mod:`argparse`.
    """

    def __init__(self, name: str = "", help: str = "") -> None:
        self.name = name
        self.help = help
        self._commands: Dict[str, Callable[..., Any]] = {}

    def command(self, name: str | None = None, *args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            cmd_name = name or func.__name__.replace("_", "-")
            self._commands[cmd_name] = func
            return func

        return decorator

    # ------------------------------------------------------------------
    def __call__(self, argv: List[str] | None = None) -> None:
        parser = argparse.ArgumentParser(prog=self.name or "app", description=self.help)
        subparsers = parser.add_subparsers(dest="command")

        # Build subparsers for each registered command
        for cmd_name, func in self._commands.items():
            sub = subparsers.add_parser(cmd_name, help=func.__doc__)
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                default = param.default
                if isinstance(default, _OptionInfo):
                    ann = param.annotation
                    if isinstance(ann, str):
                        ann = {"int": int, "float": float, "str": str, "Path": Path}.get(ann, str)
                    flags = default.flags or [f"--{param_name.replace('_', '-')}"]
                    kwargs: Dict[str, Any] = {"help": default.help}
                    if ann in {int, float, str}:
                        kwargs["type"] = ann
                    if default.required:
                        kwargs["required"] = True
                    else:
                        kwargs["default"] = default.default
                    kwargs["dest"] = param_name
                    sub.add_argument(*flags, **kwargs)
            sub.set_defaults(func=func)

        args = parser.parse_args(argv)
        if not hasattr(args, "func"):
            parser.print_help()
            return

        func = args.func
        sig = inspect.signature(func)
        call_kwargs: Dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            default = param.default
            if isinstance(default, _OptionInfo):
                value = getattr(args, param_name.replace("-", "_"))
                ann = param.annotation
                if isinstance(ann, str):
                    ann = {"Path": Path}.get(ann)
                if ann is Path:
                    value = Path(value)
                call_kwargs[param_name] = value
        func(**call_kwargs)


def echo(message: Any) -> None:  # pragma: no cover - simple print
    print(message)


__all__ = ["Typer", "Option", "echo"]


