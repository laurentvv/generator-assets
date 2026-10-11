"""Build the exact CLI argv for a job, from validated form values.

The frozen consumer contract (AGENTS.md ecosystem section): the UI invokes
`uv run python main.py -w <workflow> [prompt] [--flag value ...]` as a
subprocess from the repository root. This module only PRODUCES that argv —
spawning lives in jobs.py. Values are validated against the real argparse
surface so a tampered form can never inject arbitrary flags.
"""

import logging
from typing import Any, Dict, List, Tuple

from server import introspection

logger = logging.getLogger(__name__)


class ArgvError(ValueError):
    """Invalid parameter for this workflow (bad dest, type or choice)."""


_TRUTHY = {"1", "on", "true", "yes"}


def _truthy(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() in _TRUTHY)


def build_argv(workflow: str, params: Dict[str, Any]) -> Tuple[List[str], str]:
    """Return (flags_argv, prompt). The caller prepends `main.py -w <workflow>`.

    params maps argparse dests to values (strings from the HTML form, or
    bool/int/float/list from presets). Unknown dests raise ArgvError; empty
    values are skipped (workflows apply their own defaults — contract).
    """
    entry = introspection.get(workflow)
    if entry is None:
        raise ArgvError(f"unknown workflow: {workflow}")

    prompt = str(params.get("prompt") or "").strip()
    argv: List[str] = []

    for dest in sorted(params):
        if dest in ("prompt",):
            continue
        value = params[dest]
        if value is None or value == "" or value is False:
            continue
        param = entry["params"].get(dest)
        if param is None:
            raise ArgvError(f"parameter '{dest}' is not part of workflow '{workflow}'")

        if param["store"] == "store_true":
            if _truthy(value):
                argv.append(param["flag"])
            continue

        if param["store"] == "append":
            items = value if isinstance(value, list) else [chunk for chunk in str(value).split(",")]
            for item in items:
                item = str(item).strip()
                if item:
                    argv.extend([param["flag"], item])
            continue

        text = str(value).strip()
        if not text:
            continue
        if param["choices"] and text not in param["choices"]:
            raise ArgvError(f"'{text}' is not a valid choice for {param['flag']} ({', '.join(param['choices'])})")
        if param["type"] == "int":
            try:
                int(text)
            except ValueError as exc:
                raise ArgvError(f"{param['flag']} expects an integer") from exc
        elif param["type"] == "float":
            try:
                float(text)
            except ValueError as exc:
                raise ArgvError(f"{param['flag']} expects a number") from exc
        argv.extend([param["flag"], text])

    return argv, prompt
