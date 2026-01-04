from __future__ import annotations

from dndsim.core.engine.state import CombatantState, AttackProfile
from dndsim.api.schemas import CreatureData  # путь подстрой под себя


def combatant_from_creature_data(
    *,
    combatant_id: str,
    name: str,
    data: CreatureData,
    side: str | None = None,
    position=(0, 0),
) -> CombatantState:
    attacks = {}
    for atk_name, spec in data.attacks.items():
        attacks[atk_name] = AttackProfile(
            name=spec.name,
            to_hit_bonus=spec.to_hit_bonus,
            damage_formula=spec.damage_formula,
            damage_type=spec.damage_type,
            reach_ft=spec.reach_ft,
            uses_action=spec.uses_action,
            uses_bonus_action=spec.uses_bonus_action,
        )

    # ресурсы (если мы их добавили в CreatureData — см. ниже)
    res_cur: dict[str, int] = {}
    res_max: dict[str, int] = {}

    resources = getattr(data, "resources", None)
    if resources:
        for k, spec in resources.items():
            # spec: ResourceSpec
            res_cur[k] = int(getattr(spec, "current", 0) or 0)
            res_max[k] = int(getattr(spec, "max", 0) or 0)

    # temp hp
    temp_hp = int(getattr(data, "temp_hp", 0) or 0)

    # initiative bonus
    initiative_bonus = int(getattr(data, "initiative_bonus", 0) or 0)

    # attacks per action
    attacks_per_action = int(getattr(data, "attacks_per_action", 1) or 1)

    # is PC
    is_pc = bool(getattr(data, "is_player_character", False))

    c = CombatantState(
        id=combatant_id,
        name=name,
        ac=data.ac,
        hp_current=data.hp_max,  # стартуем с max
        hp_max=data.hp_max,
        speed_ft=data.speed_ft,
        side=side,
        position=position,
        attacks=attacks,
        # новые поля
        temp_hp=temp_hp,
        is_player_character=is_pc,
        attacks_per_action=attacks_per_action,
        initiative_bonus=initiative_bonus,
        resources_current=res_cur,
        resources_max=res_max,
    )

    # переносим resist/vuln/immune
    c.damage_resistances = set(data.damage_resistances)
    c.damage_vulnerabilities = set(data.damage_vulnerabilities)
    c.damage_immunities = set(data.damage_immunities)

    # переносим save bonuses (пока движок использует их напрямую)
    c.save_bonuses = dict(data.save_bonuses)

    # spellcasting (если есть)
    if data.spellcasting is not None:
        c.spellcasting_ability = data.spellcasting.spellcasting_ability
        c.spell_save_dc = data.spellcasting.spell_save_dc
        c.spell_attack_bonus = data.spellcasting.spell_attack_bonus
        c.spell_slots_current = dict(data.spellcasting.spell_slots_current)
        c.spell_slots_max = dict(data.spellcasting.spell_slots_max)

    return c
