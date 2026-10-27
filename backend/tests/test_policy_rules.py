import pytest


@pytest.mark.parametrize("scope,limit,owner,departments,want", [
    ("own","institution","alice",["3"],True),
    ("own","institution","bob",["3"],False),
    ("own","departments","alice",["3"],True),
    ("own","departments","alice",["4"],False),
    ("departments","own","alice",["3"],True),
    ("departments","own","bob",["3"],False),
    ("institution","departments","bob",["3"],True),
    ("institution","departments","bob",["4"],False),
    ("institution","own","alice",["4"],True),
    ("institution","own","bob",["3"],False),
])
def test_scope_limit_is_intersection_not_a_global_union(scope,limit,owner,departments,want):
    from apps.accounts.policies import AccessRule
    rule = AccessRule(scope=scope, limit=limit, department_ids=frozenset({"3"}))
    assert rule.allows("alice",employee_id=owner,department_ids=departments) is want


def test_empty_department_rule_does_not_mean_unrestricted_access():
    from apps.accounts.policies import AccessRule
    rule = AccessRule(scope="departments",limit="institution",department_ids=frozenset())
    assert rule.allows("alice",employee_id="alice",department_ids=["3"]) is False
