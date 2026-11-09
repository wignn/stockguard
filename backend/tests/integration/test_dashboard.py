from datetime import timedelta

from sqlalchemy.orm import Session
from test_approvals import cases_url, decision, prepare_case, submit


def test_dashboard_live_counts_and_tenant_scope(authenticated, staff, app):
    item, _, _ = prepare_case(authenticated, staff, app)
    url = f"/api/v1/businesses/{app.state.test_business_id}"
    response = authenticated.get(url + "/dashboard")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["active_products"] == 1
    assert result["unresolved_cases"] == 1
    assert result["high_priority_products"] == 0
    assert result["population"] == "active_products"
    assert result["products"]["total"] == 1
    risk = authenticated.get(url + f"/products/{item['id']}/risk")
    assert risk.status_code == 200 and risk.json()["priority"] == "medium"
    assert authenticated.get(url + "/dashboard?priority=high").json()["products"]["total"] == 0
    assert authenticated.get(url + "/dashboard?q=not-found").json()["products"]["total"] == 0
    assert (
        authenticated.get(f"/api/v1/businesses/{app.state.other_business_id}/dashboard").status_code
        == 404
    )


def test_late_evidence_does_not_rewrite_decision_snapshot(authenticated, staff, app):
    from stokguard.approvals.models import ApprovalDecision, CaseSubmission
    from stokguard.core.transactions import write_uow

    _, count, case = prepare_case(authenticated, staff, app)
    submitted = submit(
        staff, app, case, count, cause="unknown", resolution_kind="adjustment", movement_kind=None
    )
    assert submitted.status_code == 201
    approved = decision(authenticated, app, case, submitted.json())
    assert approved.status_code == 200
    with Session(app.state.engine) as db:
        submission = db.get(CaseSubmission, submitted.json()["id"])
        approval = db.get(ApprovalDecision, approved.json()["id"])
        snapshot = dict(approval.snapshot)
        assert submission.snapshot["priority"]["policy_version"] == "rules-v1"
        assert snapshot["priority"]["priority"] == "medium"
        assert snapshot["missing_evidence"] is True
    # Later case notes do not alter the immutable evidence/policy facts at decision time.
    with write_uow(app.state.engine) as db:
        from stokguard.investigations.models import InvestigationCase

        db.get(InvestigationCase, case["id"]).findings = "Bukti susulan tersedia"
    with Session(app.state.engine) as db:
        assert db.get(ApprovalDecision, approved.json()["id"]).snapshot == snapshot
    assert authenticated.get(f"{cases_url(app)}/{case['id']}").json()["status"] == "resolved"


def test_decision_takes_fresh_policy_snapshot(authenticated, staff, app):
    from stokguard.approvals.models import ApprovalDecision, CaseSubmission

    _, count, case = prepare_case(authenticated, staff, app)
    submitted = submit(staff, app, case, count)
    assert submitted.status_code == 201
    app.state.clock.value += timedelta(hours=1)
    approved = decision(authenticated, app, case, submitted.json())
    assert approved.status_code == 200
    with Session(app.state.engine) as db:
        submission = db.get(CaseSubmission, submitted.json()["id"])
        approval = db.get(ApprovalDecision, approved.json()["id"])
        assert approval.snapshot["priority"][
            "window_end"
        ] == app.state.clock.now().isoformat().replace("+00:00", "Z")
        assert (
            approval.snapshot["priority"]["window_end"]
            != submission.snapshot["priority"]["window_end"]
        )
