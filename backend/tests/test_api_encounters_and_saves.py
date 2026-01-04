def test_encounters_create_list_and_saves(client):
    r = client.post("/encounters", json={"name": "Test Encounter"})
    assert r.status_code == 200, r.text
    enc = r.json()
    enc_id = enc["id"]

    r = client.get("/encounters")
    assert r.status_code == 200
    assert len(r.json()) == 1

    save_payload = {
        "label": "round1",
        "state": {"round": 1, "turn_owner_id": "C", "combatants": {}},
    }
    r = client.post(f"/encounters/{enc_id}/saves", json=save_payload)
    assert r.status_code == 200, r.text
    save = r.json()
    save_id = save["id"]

    r = client.get(f"/encounters/{enc_id}/saves")
    assert r.status_code == 200
    lst = r.json()
    assert len(lst) == 1
    assert lst[0]["id"] == save_id

    r = client.get(f"/encounters/saves/{save_id}")
    assert r.status_code == 200
    loaded = r.json()
    assert loaded["id"] == save_id
    assert loaded["state"]["round"] == 1
