from __future__ import annotations

from dndsim.core.engine.spells.registry import register_spell
from dndsim.core.engine.spells.definitions import SaveSpell, AttackSpell


def register_core_spells() -> None:
    """
    Минимальный набор часто встречающихся спеллов (MVP).
    Без сложных эффектов (conditions/buffs), только:
      - SaveSpell: save half / save negates / no damage
      - AttackSpell: spell attack
      - range_ft + target_mode
      - concentration flag (каркас)
    """

    # --- AoE save-half damage ---
    register_spell(
        SaveSpell(
            name="fireball",
            economy="action",
            concentration=False,
            min_slot_level=3,
            target_mode="aoe",
            range_ft=150,
            save_ability="dex",
            on_success="half",
            damage_formula="8d6+0",
            damage_type="fire",
        )
    )

    register_spell(
        SaveSpell(
            name="burning_hands",
            economy="action",
            concentration=False,
            min_slot_level=1,
            target_mode="aoe",
            range_ft=15,
            save_ability="dex",
            on_success="half",
            damage_formula="3d6+0",
            damage_type="fire",
        )
    )

    # --- Single target save: save negates damage ---
    register_spell(
        SaveSpell(
            name="sacred_flame",
            economy="action",
            concentration=False,
            min_slot_level=0,  # cantrip
            target_mode="single",
            range_ft=60,
            save_ability="dex",
            on_success="none",
            damage_formula="1d8+0",
            damage_type="radiant",
        )
    )

    # --- “control” spell: save negates, no damage (концентрация каркас) ---
    # damage_formula/damage_type пустые => resolver пропускает урон.
    register_spell(
        SaveSpell(
            name="hold_person",
            economy="action",
            concentration=True,
            min_slot_level=2,
            target_mode="single",
            range_ft=60,
            save_ability="wis",
            on_success="none",
            damage_formula="",
            damage_type="",
            on_fail_conditions={"paralyzed"},
        )
    )

    # --- Spell attacks ---
    register_spell(
        AttackSpell(
            name="guiding_bolt",
            economy="action",
            concentration=False,
            min_slot_level=1,
            target_mode="single",
            range_ft=120,
            attack_kind="ranged",
            damage_formula="4d6+0",
            damage_type="radiant",
        )
    )

    register_spell(
        AttackSpell(
            name="ray_of_frost",
            economy="action",
            concentration=False,
            min_slot_level=0,
            target_mode="single",
            range_ft=60,
            attack_kind="ranged",
            damage_formula="1d8+0",
            damage_type="cold",
        )
    )
