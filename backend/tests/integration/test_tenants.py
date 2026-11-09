def test_cross_business_context_hidden(authenticated, app):
    own = authenticated.get(f"/api/v1/businesses/{app.state.test_business_id}")
    assert own.status_code == 200
    assert own.json()["name"] == "Test business A"
    foreign = authenticated.get(f"/api/v1/businesses/{app.state.other_business_id}")
    assert foreign.status_code == 404
    memberships = authenticated.get("/api/v1/auth/memberships").json()
    assert len(memberships) == 1
    assert memberships[0]["role"] == "owner"
