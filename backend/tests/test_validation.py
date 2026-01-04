def test_creature_validation_422(client):
    # hp_max отсутствует -> должен быть 422
    bad = {"name": "Bad", "data": {"ac": 10}}
    r = client.post("/creatures", json=bad)
    assert r.status_code == 422
