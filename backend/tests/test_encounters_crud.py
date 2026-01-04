def test_encounters_create_list_get(client):
    # create
    r = client.post("/encounters", json={"name": "Test Encounter"})
    assert r.status_code in (200, 201), r.text
    enc = r.json()
    assert "id" in enc
    eid = enc["id"]

    # list
    r = client.get("/encounters")
    assert r.status_code == 200
    items = r.json()
    assert any(x["id"] == eid for x in items)

    # get
    r = client.get(f"/encounters/{eid}")
    assert r.status_code == 200
    one = r.json()
    assert one["id"] == eid
    assert one["name"] == "Test Encounter"
