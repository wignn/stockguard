import csv
from datetime import UTC, datetime, timedelta
from io import StringIO
from uuid import uuid4

import pytest
from test_approvals import cases_url, prepare_case
from test_files import upload


def base(app, business_id=None):
    return f"/api/v1/businesses/{business_id or app.state.test_business_id}"


def make_product(client, app, sku="EXP-01"):
    response = client.post(
        base(app) + "/products",
        json={
            "sku": sku,
            "name": "Kopi Ekspor",
            "unit": "Pcs",
            "step_quantity": "1",
            "cost_rupiah": "5000",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def book(client, app, product_id, kind, quantity, version, note, occurred_at=None):
    when = (occurred_at or app.state.clock.now()).isoformat()
    response = client.post(
        base(app) + "/movements",
        json={
            "product_id": product_id,
            "kind": kind,
            "quantity": quantity,
            "occurred_at": when,
            "note": note,
            "expected_balance_version": version,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    "dangerous_note",
    [
        "=SUM(1,2)",
        "+cmd|' /C calc'!A0",
        '-potongan "khusus"\nbaris kedua',
        "@IMPORTXML(A1,A2)",
        "\t=1+1",
        "\r=2+2",
    ],
)
def test_csv_formula_injection_quotes_newlines_and_signed_quantity(
    authenticated, app, dangerous_note
):
    product = make_product(authenticated, app, sku=f"CSV-{uuid4().hex[:6]}")
    book(authenticated, app, product["id"], "inbound", "24", 0, "Stok masuk normal")
    sale = book(authenticated, app, product["id"], "sale", "6", 1, dangerous_note)

    response = authenticated.get(base(app) + "/exports/audit.csv")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["x-content-type-options"] == "nosniff"

    rows = list(csv.DictReader(StringIO(response.text)))
    sale_rows = [
        row
        for row in rows
        if row["action"] == "movement_booked" and row["entity_id"] == sale["id"]
    ]
    assert len(sale_rows) == 1
    sale_row = sale_rows[0]

    # Signed quantity is a controlled formatted numeric column, not raw text prefixed with "'"
    assert sale_row["quantity"] == "-6"
    # Text column starting with =, +, -, @, \t, \r is neutralized with leading "'"
    # and preserves quotes and newlines across RFC 4180 CSV parsing
    assert sale_row["note"] == f"'{dangerous_note}"


def test_csv_date_filter_and_foreign_business_isolation(authenticated, app):
    product = make_product(authenticated, app, sku="FILT-01")
    early_time = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
    late_time = datetime(2026, 11, 8, 10, 0, tzinfo=UTC)

    app.state.clock.value = early_time
    early = book(authenticated, app, product["id"], "inbound", "10", 0, "Awal bulan", early_time)

    app.state.clock.value = late_time
    late = book(
        authenticated,
        app,
        product["id"],
        "sale",
        "3",
        1,
        "Minggu kedua",
        late_time - timedelta(minutes=1),
    )

    filtered = authenticated.get(
        base(app) + "/exports/audit.csv",
        params={"from": "2026-11-05", "to": "2026-11-09"},
    )
    assert filtered.status_code == 200, filtered.text
    rows = list(csv.DictReader(StringIO(filtered.text)))
    entity_ids = {row["entity_id"] for row in rows}
    assert late["id"] in entity_ids
    assert early["id"] not in entity_ids

    foreign = authenticated.get(base(app, app.state.other_business_id) + "/exports/audit.csv")
    assert foreign.status_code == 404


def test_case_detail_includes_authorized_evidence_links(authenticated, staff, app):
    _, _, case = prepare_case(authenticated, staff, app)
    item = upload(staff, app, name="bukti-selisih.png").json()
    attached = staff.post(
        cases_url(app) + f"/{case['id']}/evidence",
        json={"file_id": item["id"]},
    )
    assert attached.status_code == 201, attached.text

    detail = staff.get(cases_url(app) + f"/{case['id']}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert "evidence" in body
    assert [ev["id"] for ev in body["evidence"]] == [item["id"]]
    assert body["evidence"][0]["original_name"] == "bukti-selisih.png"
    assert body["evidence"][0]["width"] == 12
    assert body["evidence"][0]["height"] == 12
