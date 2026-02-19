#!/usr/bin/env python3
"""Cheapest route planner from Haikou to Suzhou (via Shanghai or nearby cities)."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class Leg:
    mode: str
    origin: str
    destination: str
    cost: float
    duration_hours: float
    notes: str = ""


@dataclass(frozen=True)
class RoutePlan:
    strategy: str
    legs: tuple[Leg, ...]
    risks: tuple[str, ...] = ()

    @property
    def total_cost(self) -> float:
        return round(sum(leg.cost for leg in self.legs), 2)

    @property
    def total_duration(self) -> float:
        return round(sum(leg.duration_hours for leg in self.legs), 2)


CITY_TO_SUZHOU_GROUND_COST = {
    "上海": (35.0, 0.45, "上海虹桥/上海站可高铁直达苏州"),
    "杭州": (110.0, 1.4, "杭州东高铁到苏州"),
    "宁波": (145.0, 2.2, "宁波站高铁到苏州"),
    "无锡": (25.0, 0.35, "无锡到苏州城际/打车"),
    "南京": (95.0, 1.2, "南京南高铁到苏州"),
}


def load_raw_data(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_route_plans(data: dict) -> list[RoutePlan]:
    plans: list[RoutePlan] = []

    for item in data.get("direct_to_shanghai", []):
        plans.append(
            RoutePlan(
                strategy="方案① 海口直飞上海 + 到苏州",
                legs=(
                    Leg("flight", "海口", "上海", item["flight_cost"], item["flight_hours"], item.get("flight_no", "")),
                    Leg("rail", "上海", "苏州", item["rail_cost"], item["rail_hours"], "高铁"),
                ),
            )
        )

    for item in data.get("haikou_to_zhanjiang_wuchuan", []):
        plans.append(
            RoutePlan(
                strategy="方案② 海口->湛江(铁路) + 吴川飞上海 + 到苏州",
                legs=(
                    Leg("rail", "海口", "湛江", item["rail_cost"], item["rail_hours"], item.get("rail_note", "")),
                    Leg("taxi", "湛江站", "吴川机场", item["transfer_cost"], item["transfer_hours"], "站到机场"),
                    Leg("flight", "吴川", "上海", item["flight_cost"], item["flight_hours"], item.get("flight_no", "")),
                    Leg("rail", "上海", "苏州", item["rail_to_suzhou_cost"], item["rail_to_suzhou_hours"], "高铁"),
                ),
                risks=("火车票紧张时可能不可行",),
            )
        )

    for item in data.get("leave_hainan_then_transfer", []):
        transfer_city = item["transfer_city"]
        rail_cost, rail_hours, rail_note = CITY_TO_SUZHOU_GROUND_COST.get(
            transfer_city, (item.get("ground_cost", 0.0), item.get("ground_hours", 0.0), "地面接驳")
        )
        plans.append(
            RoutePlan(
                strategy=f"方案③ 先离岛({item['first_hop_to']})再转运({transfer_city})",
                legs=(
                    Leg("flight", "海口", item["first_hop_to"], item["first_hop_cost"], item["first_hop_hours"], "先离岛"),
                    Leg("flight", item["first_hop_to"], transfer_city, item["second_hop_cost"], item["second_hop_hours"], "二段航班"),
                    Leg("rail", transfer_city, "苏州", rail_cost, rail_hours, rail_note),
                ),
            )
        )

    for item in data.get("hidden_city_like", []):
        plans.append(
            RoutePlan(
                strategy="方案④ 经上海到境外（仅评估价格，不建议实际甩尾）",
                legs=(
                    Leg("flight", "海口", "上海", item["segment_cost_estimate"], item["segment_hours"], item.get("flight_no", "")),
                    Leg("rail", "上海", "苏州", item["rail_cost"], item["rail_hours"], "高铁"),
                ),
                risks=(
                    "甩尾可能违反航司规则，存在后续行程被取消或账号受限风险",
                    "托运行李无法中途取出时不可行",
                ),
            )
        )

    for item in data.get("visa_free_outbound_then_back", []):
        arrival_city = item["back_to_china_city"]
        rail_cost, rail_hours, rail_note = CITY_TO_SUZHOU_GROUND_COST.get(
            arrival_city, (item.get("ground_cost", 0.0), item.get("ground_hours", 0.0), "地面接驳"))
        plans.append(
            RoutePlan(
                strategy="方案⑤ 先飞免签国家再回国",
                legs=(
                    Leg("flight", "海口", item["country"], item["outbound_cost"], item["outbound_hours"], "离境"),
                    Leg("flight", item["country"], arrival_city, item["inbound_cost"], item["inbound_hours"], "回国"),
                    Leg("rail", arrival_city, "苏州", rail_cost, rail_hours, rail_note),
                ),
                risks=("受签证政策、入境政策与回程航班波动影响较大",),
            )
        )

    for item in data.get("extra_strategies", []):
        plans.append(
            RoutePlan(
                strategy=f"补充方案 {item['name']}",
                legs=tuple(
                    Leg(
                        seg["mode"],
                        seg["origin"],
                        seg["destination"],
                        seg["cost"],
                        seg["hours"],
                        seg.get("notes", ""),
                    )
                    for seg in item["legs"]
                ),
                risks=tuple(item.get("risks", [])),
            )
        )

    return plans


def rank_plans(plans: Iterable[RoutePlan], top_n: int = 5) -> list[RoutePlan]:
    sorted_plans = sorted(plans, key=lambda x: (x.total_cost, x.total_duration))
    return sorted_plans[:top_n]


def pretty_print(plans: list[RoutePlan]) -> None:
    for idx, plan in enumerate(plans, 1):
        print(f"\n[{idx}] {plan.strategy}")
        for leg in plan.legs:
            print(
                f"  - {leg.mode:6s} {leg.origin} -> {leg.destination} | ¥{leg.cost:.0f} | {leg.duration_hours:.2f}h {leg.notes}".rstrip()
            )
        print(f"  总价: ¥{plan.total_cost:.0f} | 总耗时: {plan.total_duration:.2f}h")
        if plan.risks:
            print("  风险提示: " + "；".join(plan.risks))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="查询海口->苏州最划算组合出行方案")
    parser.add_argument("--data", default="data/sample_options.json", help="航段与接驳报价数据 JSON 文件")
    parser.add_argument("--top", type=int, default=5, help="输出最优方案数量")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = load_raw_data(Path(args.data))
    plans = build_route_plans(data)
    best = rank_plans(plans, top_n=args.top)
    pretty_print(best)


if __name__ == "__main__":
    main()
