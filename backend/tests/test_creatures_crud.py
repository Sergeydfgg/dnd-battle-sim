def test_creatures_create_list_get_patch(client):
    payload = {
        "name": "Goblin",
        "data": {
            "ac": 15,
            "hp_max": 7,
            "speed_ft": 30,
            "ability_scores": {
                "str": 8,
                "dex": 14,
                "con": 10,
                "int": 10,
                "wis": 8,
                "cha": 8,
            },
            "proficiency_bonus": 2,
            "save_proficiencies": [],
            "save_bonuses": {"dex": 2},
            "damage_resistances": [],
            "damage_vulnerabilities": [],
            "damage_immunities": [],
            "temp_hp": 3,
            "initiative_bonus": 2,
            "is_player_character": False,
            "attacks_per_action": 1,
            "resources": {"rage": {"max": 0, "current": 0, "refresh": "long_rest"}},
            "attacks": {
                "scimitar": {
                    "name": "Scimitar",
                    "to_hit_bonus": 4,
                    "damage_formula": "1d6+2",
                    "damage_type": "slashing",
                    "reach_ft": 5,
                    "uses_action": True,
                    "uses_bonus_action": False,
                    "ability_used": "dex",
                    "proficient": True,
                    "damage_bonus": 0,
                    "add_ability_mod_to_damage": True,
                }
            },
            "spellcasting": None,
        },
    }

    # create
    r = client.post("/creatures", json=payload)
    assert r.status_code in (200, 201), r.text
    created = r.json()
    assert "id" in created
    assert created["name"] == "Goblin"
    assert created["data"]["temp_hp"] == 3
    cid = created["id"]

    # list
    r = client.get("/creatures")
    assert r.status_code == 200
    items = r.json()
    assert isinstance(items, list)
    assert any(x["id"] == cid for x in items)

    # get by id
    r = client.get(f"/creatures/{cid}")
    assert r.status_code == 200
    one = r.json()
    assert one["id"] == cid
    assert one["data"]["attacks"]["scimitar"]["damage_formula"] == "1d6+2"

    # patch
    patch = {
        "name": "Goblin Boss",
        "data": {
            **one["data"],
            "hp_max": 21,
            "temp_hp": 0,
            "attacks_per_action": 2,
        },
    }
    r = client.patch(f"/creatures/{cid}", json=patch)
    assert r.status_code == 200
    upd = r.json()
    assert upd["name"] == "Goblin Boss"
    assert upd["data"]["hp_max"] == 21
    assert upd["data"]["attacks_per_action"] == 2
