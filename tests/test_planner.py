from planner import Leg, RoutePlan, rank_plans


def test_total_cost_and_duration():
    plan = RoutePlan(
        strategy="demo",
        legs=(
            Leg("flight", "A", "B", 100, 1.2),
            Leg("rail", "B", "C", 30, 0.8),
        ),
    )
    assert plan.total_cost == 130
    assert plan.total_duration == 2.0


def test_rank_by_cost_then_duration():
    p1 = RoutePlan("p1", (Leg("flight", "A", "B", 100, 3.0),))
    p2 = RoutePlan("p2", (Leg("flight", "A", "B", 100, 2.0),))
    p3 = RoutePlan("p3", (Leg("flight", "A", "B", 80, 4.0),))

    ranked = rank_plans([p1, p2, p3], top_n=3)
    assert [p.strategy for p in ranked] == ["p3", "p2", "p1"]
