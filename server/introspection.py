"""Merge the live workflow registry with the argparse surface and the curated
UI layer into one catalog consumed by the templates and the job validator.

Introspection is read-only: the CLI contract (cli/parser.py, frozen by
tests/surface_cli.json) is never modified. Curated dests that no longer exist
in the surface are dropped with a warning (workflow evolution), and registry
workflows missing from the curated layer fall back to family defaults — the
UI keeps working when workflows are added or renamed upstream.
"""

import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional

from cli.parser import construire_parseur
from workflows import WorkflowRegistry

from server import schema_ui

logger = logging.getLogger(__name__)

# Dests that behave as flags with no value.
_STORE_TRUE = "store_true"
_APPEND = "append"


def _surface() -> Dict[str, Dict[str, Any]]:
    """dest -> action descriptor, from the real argparse surface."""
    actions: Dict[str, Dict[str, Any]] = {}
    for action in construire_parseur()._actions:
        actions[action.dest] = {
            "flags": list(action.option_strings),
            "dest": action.dest,
            "store": _store_kind(action),
            "default": action.default,
            "choices": list(action.choices) if action.choices else None,
            "type": getattr(action.type, "__name__", None),
            "help": action.help or "",
        }
    return actions


def _store_kind(action: Any) -> str:
    name = type(action).__name__
    if name == "_StoreTrueAction":
        return _STORE_TRUE
    if name == "_AppendAction":
        return _APPEND
    if name == "_StoreAction":
        return "value"
    return name  # exotic kinds stay visible, rendered as text


def _flag_display(action: Dict[str, Any]) -> str:
    flags = action["flags"]
    if not flags:
        return ""  # positional
    return max(flags, key=len)


def _widget_for(dest: str, action: Dict[str, Any]) -> str:
    if not action["flags"]:
        return "prompt"
    if dest in schema_ui.INPUT_PATH_DESTS:
        return "path"
    override = schema_ui.WIDGET_OVERRIDES.get(dest)
    if override:
        return override
    if action["store"] == _STORE_TRUE:
        return "toggle"
    if action["store"] == _APPEND:
        return "loras"
    if action["choices"]:
        return "select"
    if action["type"] in ("int", "float"):
        return "number"
    return "text"


def _label_for(dest: str, action: Dict[str, Any]) -> str:
    return dest.replace("_", " ").capitalize()


def _param(dest: str, action: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dest": dest,
        "flag": _flag_display(action),
        "label": _label_for(dest, action),
        "help": action["help"],
        "widget": _widget_for(dest, action),
        "store": action["store"],
        "type": action["type"],
        "default": action["default"],
        "choices": action["choices"],
        "path_kind": schema_ui.INPUT_PATH_DESTS.get(dest),
    }


@lru_cache(maxsize=1)
def catalog() -> Dict[str, Any]:
    surface = _surface()
    families: List[Dict[str, Any]] = []
    by_name: Dict[str, Dict[str, Any]] = {}

    for family in schema_ui.FAMILIES:
        families.append({**family, "workflows": []})

    family_index = {f["key"]: f for f in families}

    for name, wf_cls in WorkflowRegistry._workflows.items():
        meta = schema_ui.WORKFLOW_META.get(name, {})
        family_key = schema_ui.WORKFLOW_FAMILY.get(name, "utils")
        family = family_index[family_key]

        # Own declared params (matched by flag against the aggregated surface).
        own: List[Dict[str, Any]] = []
        own_dests: set = set()
        for declaration in getattr(wf_cls, "PARAMETRES", []):
            flag = declaration.get("flags", ("",))[0]
            action = next(
                (a for a in surface.values() if flag and flag in a["flags"]),
                None,
            )
            if action is None or action["dest"] in schema_ui.HIDDEN_DESTS:
                if action is None:
                    logger.warning("webui: declaration flag %s of %s not found in surface", flag, name)
                continue
            if action["dest"] in own_dests:
                continue
            own_dests.add(action["dest"])
            own.append(_param(action["dest"], action))

        # Family-shared dests, curated order, not already owned.
        shared: List[Dict[str, Any]] = []
        for dest in schema_ui.SHARED_BY_FAMILY.get(family_key, []):
            action = surface.get(dest)
            if action is None:
                logger.warning("webui: shared dest %s (%s) not in surface — dropped", dest, family_key)
                continue
            if dest in own_dests or dest in schema_ui.HIDDEN_DESTS:
                continue
            shared.append(_param(dest, action))
            own_dests.add(dest)

        # Curated primaries may pull ANY surface flag (flat table or declared
        # by another workflow): the aggregated CLI accepts them all — frozen
        # consumer contract — so the form mirrors what the CLI really takes.
        primary_names = list(meta.get("primary", []))
        primary: List[Dict[str, Any]] = []
        for dest in primary_names:
            if dest in own_dests:
                continue
            action = surface.get(dest)
            if action is None or dest in schema_ui.HIDDEN_DESTS or not action["flags"]:
                continue
            primary.append(_param(dest, action))
            own_dests.add(dest)
        # Then the workflow's own declarations named in the curated list.
        primary.extend(p for p in own if p["dest"] in primary_names and p not in primary)
        advanced = [p for p in own if p["dest"] not in primary_names]

        warnings = list(schema_ui.FAMILY_WARNINGS.get(family_key, [])) + list(meta.get("warnings", []))
        heavy = meta.get("heavy", name not in schema_ui.LIGHT_DEFAULTS)

        entry = {
            "name": name,
            "description": getattr(wf_cls, "description", name),
            "emoji": getattr(wf_cls, "emoji", "⚡"),
            "family": family_key,
            "family_label": family["label"],
            "heavy": bool(heavy),
            "estimate": meta.get("estimate", ""),
            "estimate_seconds": schema_ui.ESTIMATE_SECONDS.get(name),
            "warnings": warnings,
            "presets": meta.get("presets", []),
            "prompt": _param("prompt", surface["prompt"]),
            "output": _param("output", surface["output"]),
            "shared": shared,
            "primary": primary,
            "advanced": advanced,
        }
        # Full dest -> param map (form rendering + job validation).
        entry["params"] = {
            param["dest"]: param
            for param in (entry["prompt"], entry["output"], *shared, *primary, *advanced)
        }

        family["workflows"].append(entry)
        by_name[name] = entry

    # Warn about curated primaries that vanished (typos or upstream renames).
    for name, meta in schema_ui.WORKFLOW_META.items():
        if name not in by_name:
            logger.warning("webui: curated workflow %s not in registry", name)
            continue
        for dest in meta.get("primary", []):
            if dest not in by_name[name]["params"]:
                logger.warning("webui: curated primary %s of %s not renderable — dropped", dest, name)

    return {"families": families, "workflows": by_name}


def get(name: str) -> Optional[Dict[str, Any]]:
    return catalog()["workflows"].get(name)


def workflow_names() -> List[str]:
    return list(catalog()["workflows"].keys())
