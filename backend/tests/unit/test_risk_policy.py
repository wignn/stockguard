from datetime import UTC, datetime, timedelta

NOW = datetime(2026, 11, 9, 8, tzinfo=UTC)


def facts(**changes):
    from stokguard.risk.schemas import RiskFacts

    return RiskFacts(now=NOW, timezone="Asia/Jakarta", **changes)


def test_three_distinct_cases_high():
    from stokguard.risk.service import assess_priority

    result = assess_priority(facts(cases=[(str(i), NOW, -6000) for i in range(3)]))
    assert result.priority == "high" and result.case_count == 3
    assert result.policy_version == "rules-v1" and result.reasons


def test_three_negative_unproved_adjustments_high():
    from stokguard.risk.service import assess_priority

    result = assess_priority(
        facts(corrections=[(str(i), NOW, -1000, True, "adjustment_out") for i in range(3)])
    )
    assert result.priority == "high" and result.missing_evidence_corrections == 3


def test_submission_revisions_count_once():
    from stokguard.risk.service import assess_priority

    result = assess_priority(facts(cases=[("same-case", NOW, -6000)] * 5, active_case=True))
    assert result.priority == "medium" and result.case_count == 1


def test_three_matching_dates_low():
    from stokguard.risk.service import assess_priority

    counts = [(NOW - timedelta(days=i), 0) for i in range(3)]
    result = assess_priority(facts(counts=counts))
    assert result.priority == "low" and result.history_sufficient
    # UTC dates differ, but both are November 9 in Jakarta.
    counts = [
        (datetime(2026, 11, 8, 18, tzinfo=UTC), 0),
        (datetime(2026, 11, 9, 1, tzinfo=UTC), 0),
        (NOW - timedelta(days=2), 0),
    ]
    assert assess_priority(facts(counts=counts)).priority == "insufficient"


def test_unknown_when_insufficient():
    from stokguard.risk.service import assess_priority

    result = assess_priority(facts())
    assert result.priority == "insufficient" and not result.history_sufficient
    outside = NOW - timedelta(days=30, seconds=1)
    assert assess_priority(facts(cases=[("old", outside, -1)] * 3)).case_count == 0


def test_normal_sales_excluded():
    from stokguard.risk.service import assess_priority

    result = assess_priority(
        facts(corrections=[(str(i), NOW, -1000, True, "sale") for i in range(5)])
    )
    assert result.missing_evidence_corrections == 0 and result.priority == "insufficient"


def test_window_includes_boundaries_excludes_future():
    from stokguard.risk.service import assess_priority

    result = assess_priority(
        facts(
            cases=[
                ("start", NOW - timedelta(days=30), -1),
                ("end", NOW, -1),
                ("future", NOW + timedelta(seconds=1), -1),
            ]
        )
    )
    assert result.case_count == 2
