from __future__ import annotations
import inspect


from dataclasses import dataclass
from collections.abc import Mapping as ABCMapping
from typing import Any, Mapping, Optional, Type, TypeVar, get_args, get_origin, cast

# NOTE:
# Эти импорты соответствуют структуре, описанной в отчёте.
# Если у тебя классы лежат в другом модуле — поправь пути импорта.
from dndsim.api.schemas import CreatureData  # type: ignore
from dndsim.core.engine.state import CombatantState  # type: ignore

from dataclasses import dataclass
from typing import Optional


TModel = TypeVar("TModel")


@dataclass(frozen=True)
class CombatantOverrides:
    hp_current: Optional[int] = None
    temp_hp: Optional[int] = None

    # Ваша модель хранит ресурсы раздельно (current/max)
    resources_current: Optional[dict[str, int]] = None
    resources_max: Optional[dict[str, int]] = None

    # is_pc -> is_player_character
    is_player_character: Optional[bool] = None

    attacks_per_action: Optional[int] = None
    initiative_bonus: Optional[int] = None

    # опционально, удобно для тестов/рантайма
    speed_ft: Optional[int] = None


def _as_dict(obj: Any) -> dict[str, Any]:
    """
    Превращает вход (pydantic v2 model / pydantic v1 model / dict / orm-like) в dict[str, Any].
    Pylance-friendly: без сомнительных dict(res) по object.
    """
    if obj is None:
        return {}

    if isinstance(obj, dict):
        return cast(dict[str, Any], obj)

    # pydantic v2
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        res = dump()
        if isinstance(res, dict):
            return cast(dict[str, Any], res)
        if isinstance(res, ABCMapping):
            return dict(cast(ABCMapping[str, Any], res))
        return {}

    # pydantic v1
    dump_v1 = getattr(obj, "dict", None)
    if callable(dump_v1):
        res = dump_v1()
        if isinstance(res, dict):
            return cast(dict[str, Any], res)
        if isinstance(res, ABCMapping):
            return dict(cast(ABCMapping[str, Any], res))
        return {}

    # last resort (orm-like)
    out: dict[str, Any] = {}
    for k in dir(obj):
        if k.startswith("_"):
            continue
        try:
            v = getattr(obj, k)
        except Exception:
            continue
        if callable(v):
            continue
        out[k] = v
    return out


def _placeholder_for_annotation(ann: Any) -> Any:
    """
    Пытаемся подобрать безопасный placeholder для обязательных полей CombatantState,
    если мы не знаем о них заранее.
    """
    if ann is None:
        return None

    origin = get_origin(ann)
    args = get_args(ann)

    # Optional[T] => Union[T, None]
    if origin is Optional or (origin is None and args and type(None) in args):
        # берём первый не-None тип
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _placeholder_for_annotation(non_none[0])
        return None

    if ann in (int,):
        return 0
    if ann in (float,):
        return 0.0
    if ann in (bool,):
        return False
    if ann in (str,):
        return ""
    if origin in (list, tuple, set):
        return []
    if origin in (dict, Mapping):
        return {}

    # Если это pydantic модель/класс — оставим None, вдруг допускается
    return None


def _build_model(model_cls: Type[TModel], data: dict[str, Any]) -> TModel:
    """
    Создаёт экземпляр модели:
    - pydantic v2: model_validate
    - pydantic v1: parse_obj
    - dataclass/обычный класс: __init__(**filtered_kwargs)

    Фильтрация kwargs нужна, потому что CombatantState/AttackProfile у вас не обязаны принимать всё.
    """
    mv = getattr(model_cls, "model_validate", None)
    if callable(mv):
        return cast(TModel, mv(data))

    po = getattr(model_cls, "parse_obj", None)
    if callable(po):
        return cast(TModel, po(data))

    # dataclass/обычный класс — фильтруем kwargs
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


def _accepts_kw(model_cls: Type[Any], key: str) -> bool:
    """
    Проверяет, принимает ли конструктор класса keyword-аргумент `key`.
    Работает для dataclass/обычных классов.
    """
    try:
        sig = inspect.signature(model_cls)
        params = sig.parameters
        if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
            return True
        return key in params
    except Exception:
        return False


def _ensure_required_fields(
    model_cls: Type[TModel], data: dict[str, Any]
) -> dict[str, Any]:
    """
    Подкладывает значения для обязательных полей pydantic-модели, если мы их не заполнили.
    Это сильно снижает хрупкость при несовпадении схем, но ключевые поля мы всё равно маппим явно.
    """
    fields = getattr(model_cls, "model_fields", None)
    if not fields:
        return data

    for name, finfo in fields.items():
        # если уже есть — ок
        if name in data and data[name] is not None:
            continue

        # если у поля есть default — используем
        default = getattr(finfo, "default", None)
        if default is not None:
            data[name] = default
            continue

        # если default_factory — попробуем вызвать
        default_factory = getattr(finfo, "default_factory", None)
        if callable(default_factory):
            try:
                data[name] = default_factory()
                continue
            except Exception:
                pass

        # если поле обязательное — подставим placeholder по типу
        is_required = getattr(finfo, "is_required", None)
        if callable(is_required):
            required = is_required()
        else:
            # pydantic иногда хранит required иначе — если нет дефолта, считаем required
            required = True

        if required:
            ann = getattr(finfo, "annotation", None)
            data[name] = _placeholder_for_annotation(ann)

    return data


def _first_present(d: ABCMapping[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def combatant_from_creature(
    creature: CreatureData | ABCMapping[str, Any] | Any,
    *,
    combatant_id: str,
    side: str,
    position: tuple[int, int] = (0, 0),
    overrides: CombatantOverrides | None = None,
) -> CombatantState:
    c = _as_dict(creature)
    ov = overrides or CombatantOverrides()

    # --- базовые поля ---
    name = _first_present(c, "name", "title", default="Unknown")
    ac = int(_first_present(c, "ac", "armor_class", default=10))

    hp_max = int(_first_present(c, "hp_max", "hp", "hit_points", default=1))
    hp_current = hp_max
    if ov.hp_current is not None:
        hp_current = int(ov.hp_current)

    temp_hp = int(_first_present(c, "temp_hp", default=0))
    if ov.temp_hp is not None:
        temp_hp = int(ov.temp_hp)

    speed_ft = int(_first_present(c, "speed_ft", "speed", default=30))
    if ov.speed_ft is not None:
        speed_ft = int(ov.speed_ft)

    attacks_per_action = int(_first_present(c, "attacks_per_action", default=1))
    if ov.attacks_per_action is not None:
        attacks_per_action = int(ov.attacks_per_action)

    initiative_bonus = int(_first_present(c, "initiative_bonus", default=0))
    if ov.initiative_bonus is not None:
        initiative_bonus = int(ov.initiative_bonus)

    # --- is_pc -> is_player_character ---
    is_player_character = bool(
        _first_present(c, "is_player_character", "is_pc", default=False)
    )
    if ov.is_player_character is not None:
        is_player_character = bool(ov.is_player_character)

    # --- resist/vuln/immune -> damage_* sets ---
    resistances = _first_present(
        c, "damage_resistances", "resistances", "resist", default=[]
    )
    vulnerabilities = _first_present(
        c, "damage_vulnerabilities", "vulnerabilities", "vuln", default=[]
    )
    immunities = _first_present(
        c, "damage_immunities", "immunities", "immune", default=[]
    )

    damage_resistances = set(resistances or [])
    damage_vulnerabilities = set(vulnerabilities or [])
    damage_immunities = set(immunities or [])

    # --- save bonuses ---
    save_bonuses = _first_present(c, "save_bonuses", "saving_throws", default={}) or {}

    # --- spellcasting (если CreatureData хранит иначе — просто останется None/пусто) ---
    sc = _first_present(c, "spellcasting", default=None) or {}
    if not isinstance(sc, dict):
        sc = _as_dict(sc)

    spellcasting_ability = sc.get("spellcasting_ability") or sc.get("ability")
    spell_save_dc = sc.get("spell_save_dc") or sc.get("save_dc")
    spell_attack_bonus = sc.get("spell_attack_bonus") or sc.get("attack_bonus")
    spell_slots_current = sc.get("spell_slots_current") or sc.get("slots_current") or {}
    spell_slots_max = sc.get("spell_slots_max") or sc.get("slots_max") or {}

    # нормализуем слоты к Dict[int,int]
    def _slots_norm(x: Any) -> dict[int, int]:
        if not isinstance(x, dict):
            return {}
        out: dict[int, int] = {}
        for k, v in x.items():
            try:
                out[int(k)] = int(v)
            except Exception:
                continue
        return out

    spell_slots_current = _slots_norm(spell_slots_current)
    spell_slots_max = _slots_norm(spell_slots_max)

    # --- resources -> resources_current/resources_max ---
    resources = _first_present(c, "resources", default=None)
    resources_current = _first_present(c, "resources_current", default=None)
    resources_max = _first_present(c, "resources_max", default=None)

    if resources_current is None and isinstance(resources, dict):
        resources_current = resources
    if resources_max is None and isinstance(resources, dict):
        resources_max = resources

    if ov.resources_current is not None:
        resources_current = ov.resources_current
    if ov.resources_max is not None:
        resources_max = ov.resources_max

    resources_current = resources_current if isinstance(resources_current, dict) else {}
    resources_max = resources_max if isinstance(resources_max, dict) else {}

    # --- attacks: ожидается Dict[str, AttackProfile] ---
    raw_attacks = _first_present(c, "attacks", default={}) or {}
    attacks: dict[str, Any] = {}

    if isinstance(raw_attacks, list):
        # list[dict] -> dict[name] = dict
        for a in raw_attacks:
            if not isinstance(a, dict):
                a = _as_dict(a)
            aname = a.get("name") or a.get("id") or "attack"
            attacks[str(aname)] = a
    elif isinstance(raw_attacks, dict):
        # если уже dict — оставляем
        attacks = raw_attacks
    else:
        attacks = {}

    # multiattacks (если есть)
    multiattacks = (
        _first_present(c, "multiattacks", "multiattack_profiles", default={}) or {}
    )
    if not isinstance(multiattacks, dict):
        multiattacks = {}

    # position у вас: Pos = (x, y)
    pos = (int(position[0]), int(position[1]))

    data: dict[str, Any] = {
        "id": combatant_id,
        "name": name,
        "ac": ac,
        "hp_current": hp_current,
        "hp_max": hp_max,
        "temp_hp": temp_hp,
        "speed_ft": speed_ft,
        "side": side,
        "save_bonuses": save_bonuses,
        "damage_resistances": damage_resistances,
        "damage_vulnerabilities": damage_vulnerabilities,
        "damage_immunities": damage_immunities,
        "is_player_character": is_player_character,
        "attacks_per_action": attacks_per_action,
        "multiattacks": multiattacks,
        "position": pos,
        "initiative_bonus": initiative_bonus,
        "resources_current": resources_current,
        "resources_max": resources_max,
        "attacks": attacks,
        # spellcasting bits
        "spellcasting_ability": spellcasting_ability,
        "spell_save_dc": spell_save_dc,
        "spell_attack_bonus": spell_attack_bonus,
        "spell_slots_current": spell_slots_current,
        "spell_slots_max": spell_slots_max,
    }

    # создаём CombatantState через фильтрующий билдер
    return _build_model(CombatantState, data)


def creature_data_from_combatant(combatant: CombatantState) -> dict[str, Any]:
    """
    Опционально (на будущее).
    Пока возвращаем dict — пригодится позже для "сохранить изменённое существо".
    """
    d = _as_dict(combatant)
    # Умышленно оставляем минимально
    return {
        "name": d.get("name"),
        "ac": d.get("ac"),
        "hp_max": d.get("hp_max"),
        "temp_hp": d.get("temp_hp", 0),
        "resources": d.get("resources", {}),
        "is_pc": d.get("is_pc", False),
        "attacks_per_action": d.get("attacks_per_action", 1),
        "initiative_bonus": d.get("initiative_bonus", 0),
        "attacks": d.get("attacks", []),
        "spellcasting": d.get("spellcasting"),
        "resistances": d.get("resistances", []),
        "vulnerabilities": d.get("vulnerabilities", []),
        "immunities": d.get("immunities", []),
        "save_bonuses": d.get("save_bonuses", {}),
    }
