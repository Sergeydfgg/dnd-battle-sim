def test_encounter_saves_create_list_get_with_state(client):
    # create encounter
    r = client.post("/encounters", json={"name": "Save Encounter"})
    assert r.status_code in (200, 201), r.text
    eid = r.json()["id"]

    state = {
        "round": 1,
        "turn_owner_id": "C",
        "combatants": {"C": {"hp_current": 10}, "T": {"hp_current": 5}},
        "initiative_order": ["C", "T"],
    }

    # create save
    r = client.post(f"/encounters/{eid}/saves", json={"label": "s1", "state": state})
    assert r.status_code in (200, 201), r.text
    saved = r.json()
    assert "id" in saved
    sid = saved["id"]
    assert saved["encounter_id"] == eid
    assert saved["label"] == "s1"

    # list saves
    r = client.get(f"/encounters/{eid}/saves")
    assert r.status_code == 200
    items = r.json()
    assert any(x["id"] == sid for x in items)

    # get save with state
    r = client.get(f"/encounters/{eid}/saves/{sid}")
    assert r.status_code == 200
    full = r.json()
    assert full["id"] == sid
    assert full["state"]["turn_owner_id"] == "C"
    assert full["state"]["combatants"]["T"]["hp_current"] == 5
