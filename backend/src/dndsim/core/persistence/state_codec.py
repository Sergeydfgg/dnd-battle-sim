from __future__ import annotations

import inspect
from dataclasses import asdict, is_dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type, TypeVar, cast

from dndsim.core.engine.state import (
    EncounterState,
    CombatantState,
    ReactionWindow,
    Pos,
    # ниже классы могут существовать в вашем state.py; если вдруг их нет — код всё равно не упадёт
)

TModel = TypeVar("TModel")


# ---------- универсальные helpers ----------


def _build_model(model_cls: Type[TModel], data: dict[str, Any]) -> TModel:
    """Создать объект pydantic/dataclass/обычного класса, фильтруя kwargs по сигнатуре."""
    mv = getattr(model_cls, "model_validate", None)
    if callable(mv):
        return cast(TModel, mv(data))

    po = getattr(model_cls, "parse_obj", None)
    if callable(po):
        return cast(TModel, po(data))

    sig = inspect.signature(model_cls)
    params = sig.parameters

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return cast(TModel, model_cls(**data))

    allowed = {
        name
        for name, p in params.items()
        if p.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }
    filtered = {k: v for k, v in data.items() if k in allowed}
    return cast(TModel, model_cls(**filtered))


def _jsonable(v: Any) -> Any:
    """Привести значение к JSON-дружелюбному виду (set->list, tuple->list, dataclass/pydantic->dict)."""
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, set):
        return [_jsonable(x) for x in v]
    if isinstance(v, tuple):
        return [_jsonable(x) for x in v]
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(val) for k, val in v.items()}

    md = getattr(v, "model_dump", None)
    if callable(md):
        out = md()
        return _jsonable(out)

    dct = getattr(v, "dict", None)
    if callable(dct):
        out = dct()
        return _jsonable(out)

    if is_dataclass(v) and not isinstance(v, type):
        # asdict принимает только ИНСТАНС dataclass, не класс
        return _jsonable(asdict(cast(Any, v)))

    # fallback: объект с атрибутами
    try:
        return {
            k: _jsonable(getattr(v, k))
            for k in dir(v)
            if not k.startswith("_") and not callable(getattr(v, k))
        }
    except Exception:
        return str(v)


def _as_set(v: Any) -> set[str]:
    if v is None:
        return set()
    if isinstance(v, set):
        return set(cast(set[Any], v))
    if isinstance(v, (list, tuple)):
        return set(str(x) for x in v)
    return {str(v)}


def _as_pos(v: Any) -> Pos:
    if isinstance(v, tuple) and len(v) == 2:
        return (int(v[0]), int(v[1]))
    if isinstance(v, list) and len(v) == 2:
        return (int(v[0]), int(v[1]))
    if isinstance(v, dict) and "x" in v and "y" in v:
        return (int(v["x"]), int(v["y"]))
    return (0, 0)


def _int_key_dict(v: Any) -> dict[int, int]:
    if not isinstance(v, dict):
        return {}
    out: dict[int, int] = {}
    for k, val in v.items():
        try:
            out[int(k)] = int(val)
        except Exception:
            continue
    return out


# ---------- Combatant codec ----------


def combatant_to_dict(c: CombatantState) -> dict[str, Any]:
    return cast(dict[str, Any], _jsonable(c))


def combatant_from_dict(d: dict[str, Any]) -> CombatantState:
    dd = dict(d)

    # normalize sets
    dd["damage_resistances"] = _as_set(dd.get("damage_resistances"))
    dd["damage_vulnerabilities"] = _as_set(dd.get("damage_vulnerabilities"))
    dd["damage_immunities"] = _as_set(dd.get("damage_immunities"))
    dd["conditions"] = _as_set(dd.get("conditions"))

    # position
    dd["position"] = _as_pos(dd.get("position"))

    # spell slots keys int
    dd["spell_slots_current"] = _int_key_dict(dd.get("spell_slots_current"))
    dd["spell_slots_max"] = _int_key_dict(dd.get("spell_slots_max"))

    # attacks/multiattacks оставляем как dict-структуры — CombatantState сам примет/отфильтрует через _build_model
    return _build_model(CombatantState, dd)


# ---------- ReactionWindow codec ----------


def reaction_window_to_dict(rw: ReactionWindow) -> dict[str, Any]:
    return cast(dict[str, Any], _jsonable(rw))


def reaction_window_from_dict(d: dict[str, Any]) -> ReactionWindow:
    return _build_model(ReactionWindow, d)


# ---------- EncounterState codec ----------


def encounter_state_to_dict(state: EncounterState) -> dict[str, Any]:
    """
    Сериализуем EncounterState так, чтобы можно было восстановить объект и продолжить бой.
    Важно: сохраняем rng_state.
    """
    base = cast(dict[str, Any], _jsonable(state))

    # rng state (чтобы броски продолжались корректно)
    rng = getattr(state, "rng", None)
    if rng is not None:
        getstate = getattr(rng, "getstate", None)
        if callable(getstate):
            try:
                base["rng_state"] = _jsonable(getstate())
            except Exception:
                pass

    return base


def encounter_state_from_dict(d: dict[str, Any]) -> EncounterState:
    """
    Восстанавливаем EncounterState объект из dict снапшота.
    """
    dd = dict(d)

    # combatants
    combatants_raw = dd.get("combatants") or {}
    combatants: dict[str, CombatantState] = {}
    if isinstance(combatants_raw, dict):
        for cid, cdict in combatants_raw.items():
            if isinstance(cdict, dict):
                combatants[str(cid)] = combatant_from_dict(cdict)
            else:
                # fallback: SimpleNamespace
                combatants[str(cid)] = cast(
                    CombatantState, SimpleNamespace(**cast(dict, cdict))
                )
    dd["combatants"] = combatants

    # effects: если нет точного класса, используем SimpleNamespace, чтобы работал доступ по атрибутам
    effects_raw = dd.get("effects") or {}
    if isinstance(effects_raw, dict):
        effects_out: dict[str, Any] = {}
        for eid, edict in effects_raw.items():
            if isinstance(edict, dict):
                effects_out[str(eid)] = SimpleNamespace(**edict)
            else:
                effects_out[str(eid)] = edict
        dd["effects"] = effects_out

    # reaction_window
    rw = dd.get("reaction_window")
    if isinstance(rw, dict):
        try:
            dd["reaction_window"] = reaction_window_from_dict(rw)
        except Exception:
            dd["reaction_window"] = SimpleNamespace(**rw)

    # initiative structures обычно простые dict/list — оставляем как есть

    # build EncounterState
    st = _build_model(EncounterState, dd)

    # restore rng state
    rng_state = dd.get("rng_state")
    rng = getattr(st, "rng", None)
    if rng_state is not None and rng is not None:
        setstate = getattr(rng, "setstate", None)
        if callable(setstate):
            try:
                setstate(rng_state)
            except Exception:
                pass

    return st
