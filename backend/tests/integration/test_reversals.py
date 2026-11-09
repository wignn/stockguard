from uuid import uuid4

from test_ledger import create_item, movement_url, payload, post


def request_reversal(client, app, movement, version=1):
    return client.post(
        f"{movement_url(app)}/{movement['id']}/reversal-requests",
        json={"reason": "Transaksi dicatat keliru", "expected_balance_version": version},
    )


def decide(client, app, request, version=1, key=None):
    return client.post(
        f"/api/v1/businesses/{app.state.test_business_id}/reversal-requests/{request['id']}/decisions",
        json={
            "expected_request_version": request["version"],
            "expected_balance_version": version,
            "decision": "approve",
            "note": "Diperiksa",
        },
        headers={"Idempotency-Key": str(key or uuid4())},
    )


def test_reversal_requires_other_owner_approval(authenticated, staff, app):
    item = create_item(authenticated, app)
    movement = post(authenticated, app, payload(app, item)).json()
    requested = request_reversal(authenticated, app, movement)
    assert requested.status_code == 201, requested.text
    assert decide(authenticated, app, requested.json()).status_code == 403
    assert decide(staff, app, requested.json()).status_code == 403


def test_reversal_keeps_original_and_links_inverse(authenticated, staff, app):
    item = create_item(authenticated, app)
    movement = post(authenticated, app, payload(app, item)).json()
    requested = request_reversal(staff, app, movement)
    assert requested.status_code == 201, requested.text
    key = uuid4()
    response = decide(authenticated, app, requested.json(), key=key)
    assert response.status_code == 200, response.text
    assert decide(authenticated, app, requested.json(), key=key).json() == response.json()
    history = authenticated.get(movement_url(app)).json()
    assert history["total"] == 2
    inverse = next(m for m in history["items"] if m["source_type"] == "reversal")
    assert inverse["source_id"] == movement["id"]
    assert inverse["quantity"] == "-24" and inverse["balance_quantity"] == "0"
    assert authenticated.get(f"{movement_url(app)}/{movement['id']}").json() == movement
    assert request_reversal(staff, app, inverse, 2).status_code == 409
    requests = authenticated.get(
        f"/api/v1/businesses/{app.state.test_business_id}/reversal-requests"
    )
    assert requests.status_code == 200 and requests.json()["total"] == 1


def test_reversal_cannot_oversell_or_repeat(authenticated, staff, app):
    item = create_item(authenticated, app)
    movement = post(authenticated, app, payload(app, item)).json()
    assert post(authenticated, app, payload(app, item, "sale", "20", 1)).status_code == 201
    requested = request_reversal(staff, app, movement, 2)
    assert requested.status_code == 201, requested.text
    assert decide(authenticated, app, requested.json(), 2).status_code == 409
    assert request_reversal(staff, app, movement, 2).status_code == 409
