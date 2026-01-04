def test_creatures_create_list_update(client):
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
            "attacks": {
                "scimitar": {
                    "name": "Scimitar",
                    "to_hit_bonus": 4,
                    "damage_formula": "1d6+2",
                    "damage_type": "slashing",
                    "reach_ft": 5,
                    "uses_action": True,
                    "uses_bonus_action": False,
                }
            },
            "spellcasting": None,
            "temp_hp": 0,
            "initiative_bonus": 2,
            "is_player_character": False,
            "attacks_per_action": 1,
            "resources": {},
        },
    }

    r = client.post("/creatures", json=payload)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["name"] == "Goblin"
    cid = created["id"]
    assert created["data"]["initiative_bonus"] == 2
    assert created["data"]["attacks"]["scimitar"]["damage_formula"] == "1d6+2"

    r = client.get("/creatures")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["id"] == cid

    # update (name + data partial)
    upd = {
        "name": "Goblin Boss",
        "data": {
            **payload["data"],
            "temp_hp": 5,
            "resources": {"rage": {"max": 2, "current": 2, "refresh": "long_rest"}},
        },
    }
    r = client.put(f"/creatures/{cid}", json=upd)
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["name"] == "Goblin Boss"
    assert updated["data"]["temp_hp"] == 5
    assert updated["data"]["resources"]["rage"]["max"] == 2
