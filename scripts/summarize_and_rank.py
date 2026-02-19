#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DATA_PATH = Path("data/sample_options.json")


def _f(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def money(x: float) -> str:
    s = f"{x:.2f}"
    s = s.rstrip("0").rstrip(".")
    return f"¥{s}"


def hours(x: float) -> str:
    s = f"{x:.2f}"
    s = s.rstrip("0").rstrip(".")
    return f"{s}h"


def extract_date_from_key_or_name(text: str) -> str:
    """
    尝试从 price_key / name / notes 里提取日期：
    - key: *_20260227
    - notes/name: 2026-02-27
    """
    if not text:
        return "-"
    m = re.search(r"_(20\d{6})\b", text)
    if m:
        ymd = m.group(1)
        return f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"
    m = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    return "-"


@dataclass
class Leg:
    mode: str
    origin: str
    destination: str
    cost: float
    hrs: float
    price_key: str = ""
    notes: str = ""


@dataclass
class RouteRow:
    category: str
    name: str
    date: str
    total_cost: float
    total_hours: float
    detail: str


def leg_desc(l: Leg) -> str:
    od = ""
    if l.origin or l.destination:
        od = f"{l.origin}→{l.destination}"
    extras = []
    if l.price_key:
        extras.append(f"key={l.price_key}")
    if l.notes:
        extras.append(l.notes)
    extra = f" [{' / '.join(extras)}]" if extras else ""
    return f"{l.mode}:{od} ({money(l.cost)}, {hours(l.hrs)}){extra}"


def add_route(rows: List[RouteRow], category: str, name: str, legs: List[Leg], date_hint: str = ""):
    total_cost = sum(l.cost for l in legs)
    total_hours = sum(l.hrs for l in legs)
    # 尽量从 price_key / name / notes 里提日期
    date = "-"
    if date_hint:
        date = extract_date_from_key_or_name(date_hint)
    if date == "-":
        for l in legs:
            date = extract_date_from_key_or_name(l.price_key) or "-"
            if date != "-":
                break
    if date == "-":
        date = extract_date_from_key_or_name(name)

    detail = "； ".join(leg_desc(l) for l in legs)
    rows.append(RouteRow(category, name, date, total_cost, total_hours, detail))


def load_json() -> Dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def build_rows(data: Dict[str, Any]) -> List[RouteRow]:
    rows: List[RouteRow] = []

    # 1) direct_to_shanghai: flight + rail
    for item in data.get("direct_to_shanghai", []):
        key = str(item.get("price_key", ""))
        legs = [
            Leg(
                mode="flight",
                origin="HAK",
                destination="SHA/PVG",
                cost=_f(item.get("flight_cost")),
                hrs=_f(item.get("flight_hours")),
                price_key=key,
                notes=str(item.get("flight_no", "")),
            ),
            Leg(
                mode="rail",
                origin="上海",
                destination="苏州",
                cost=_f(item.get("rail_cost")),
                hrs=_f(item.get("rail_hours")),
                notes="固定成本",
            ),
        ]
        add_route(rows, "direct_to_shanghai", "海口→上海→苏州（直飞+高铁）", legs, date_hint=key)

    # 2) haikou_to_zhanjiang_wuchuan: rail + transfer + flight + rail
    for item in data.get("haikou_to_zhanjiang_wuchuan", []):
        key = str(item.get("price_key", ""))
        legs = [
            Leg("rail", "海口", "湛江", _f(item.get("rail_cost")), _f(item.get("rail_hours")), notes=str(item.get("rail_note", "固定成本"))),
            Leg("taxi", "湛江站", "吴川机场", _f(item.get("transfer_cost")), _f(item.get("transfer_hours")), notes="固定成本"),
            Leg("flight", "ZHA", "SHA", _f(item.get("flight_cost")), _f(item.get("flight_hours")), price_key=key, notes=str(item.get("flight_no", ""))),
            Leg("rail", "上海", "苏州", _f(item.get("rail_to_suzhou_cost")), _f(item.get("rail_to_suzhou_hours")), notes="固定成本"),
        ]
        add_route(rows, "haikou_to_zhanjiang_wuchuan", "海口→湛江→上海→苏州（火车+转场+飞）", legs, date_hint=key)

    # 3) leave_hainan_then_transfer: two flights
    for item in data.get("leave_hainan_then_transfer", []):
        k1 = str(item.get("first_hop_price_key", ""))
        k2 = str(item.get("second_hop_price_key", ""))
        legs = [
            Leg("flight", "HAK", str(item.get("first_hop_to", "")), _f(item.get("first_hop_cost")), _f(item.get("first_hop_hours")), price_key=k1),
            Leg("flight", str(item.get("first_hop_to", "")), str(item.get("transfer_city", "")), _f(item.get("second_hop_cost")), _f(item.get("second_hop_hours")), price_key=k2),
        ]
        add_route(rows, "leave_hainan_then_transfer", f"海口→{item.get('first_hop_to','')}→{item.get('transfer_city','')}（两段中转）", legs, date_hint=k1 or k2)

    # 4) extra_strategies: legs already structured
    for item in data.get("extra_strategies", []):
        name = str(item.get("name", "extra"))
        legs: List[Leg] = []
        date_hint = name
        for l in item.get("legs", []):
            price_key = str(l.get("price_key", ""))
            notes = str(l.get("notes", ""))
            if price_key:
                date_hint = date_hint + " " + price_key
            if notes:
                date_hint = date_hint + " " + notes
            legs.append(
                Leg(
                    mode=str(l.get("mode", "")),
                    origin=str(l.get("origin", "")),
                    destination=str(l.get("destination", "")),
                    cost=_f(l.get("cost")),
                    hrs=_f(l.get("hours")),
                    price_key=price_key,
                    notes=notes,
                )
            )
        add_route(rows, "extra_strategies", name, legs, date_hint=date_hint)

    return rows


def to_markdown(rows: List[RouteRow]) -> str:
    # 按总价、总时长排序
    rows_sorted = sorted(rows, key=lambda r: (r.total_cost, r.total_hours, r.name))

    header = (
        "| 排名 | 日期 | 方案 | 总价 | 总时长 | 明细 |\n"
        "|---:|---|---|---:|---:|---|\n"
    )
    lines = []
    for i, r in enumerate(rows_sorted, 1):
        lines.append(
            f"| {i} | {r.date} | {r.name} | {money(r.total_cost)} | {hours(r.total_hours)} | {r.detail} |"
        )
    return header + "\n".join(lines) + "\n"


def main():
    data = load_json()
    rows = build_rows(data)

    md = to_markdown(rows)
    print(md)

    Path("summary.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
