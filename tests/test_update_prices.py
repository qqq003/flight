from scripts.update_prices import PriceResult, apply_price_updates, resolve_queries


def test_resolve_queries():
    config = {
        "routes": [
            {"key": "hak_sha", "origin": "HAK", "destination": "SHA", "date_offset_days": 5}
        ]
    }
    queries = resolve_queries(config)
    assert len(queries) == 1
    assert queries[0].key == "hak_sha"
    assert queries[0].origin == "HAK"
    assert queries[0].destination == "SHA"
    assert queries[0].date_offset_days == 5


def test_apply_price_updates():
    data = {
        "direct_to_shanghai": [{"flight_cost": 500, "price_key": "k1"}],
        "haikou_to_zhanjiang_wuchuan": [{"flight_cost": 300, "price_key": "k2"}],
        "leave_hainan_then_transfer": [
            {"first_hop_cost": 200, "second_hop_cost": 220, "first_hop_price_key": "k3", "second_hop_price_key": "k4"}
        ],
        "extra_strategies": [
            {
                "legs": [
                    {"mode": "flight", "cost": 100, "price_key": "k5"},
                    {"mode": "rail", "cost": 20},
                ]
            }
        ],
    }
    results = [
        PriceResult("k1", 501.6, "CNY"),
        PriceResult("k2", 320.0, "CNY"),
        PriceResult("k3", 180.2, "CNY"),
        PriceResult("k4", 260.8, "CNY"),
        PriceResult("k5", 99.9, "CNY"),
    ]

    updated = apply_price_updates(data, results)

    assert updated["direct_to_shanghai"][0]["flight_cost"] == 501.6
    assert updated["haikou_to_zhanjiang_wuchuan"][0]["flight_cost"] == 320.0
    assert updated["leave_hainan_then_transfer"][0]["first_hop_cost"] == 180.2
    assert updated["leave_hainan_then_transfer"][0]["second_hop_cost"] == 260.8
    assert updated["extra_strategies"][0]["legs"][0]["cost"] == 99.9
