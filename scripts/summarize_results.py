#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


DATA_PATH = Path("data/sample_options.json")


def money(x: float) -> str:
    # 统一格式
    if x is None:
        return "-"
    return f"¥{x:.2f}".rstrip("0").rstrip(".")


def hours(x: float) -> str:
    if x is None:
        return "-"
    return f"{x:.2f}h".rstrip("0").rstrip(".")


def load() -> Dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def add_row(rows: List[Dict[str, Any]], category: str, name: str, legs: List[Dict[str, Any]], notes: str = ""):
    total_cost = sum(float(l.get("cost", 0.0) or 0.0) for l in legs)
    total_hours = sum(float(l.get("hours", 0.0) or 0.0) for l in legs)

    detail_parts = []
    for l in legs:
        mode = l.get("mode", "?")
        od = ""
        if l.get("origin") and l.get("destination"):
            od = f"{l['origin']}→{l['destination']}"
        extra = []
        if l.get("flight_no"):
            extra.append(str(l["flight_no"]))
        if l.get("price_key"):
            extra.append(f"key={l['price_key']}")
        if l.get("notes"):
            extra.append(str(l["notes"]))
        extra_s = (" | " + " / ".join(extra)) if extra else ""
        detail_parts.append(f"{mode}:{od}{extra_s} ({money(float(l.get('cost',0) or 0))}, {hours(float(l.get('hours',0) or 0))})")

    rows.append(
        {
            "category": category,
            "name": name,
            "total_cost": total_cost,
            "total_hours": total_hours,
            "detail": "； ".join(detail_parts),
            "notes": notes,
        }
    )


def summarize(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    # 1) direct_to_shanghai：flight + rail
    for item in data.get("direct_to_shanghai", []):
        legs = [
            {
                "mode": "flight",
                "origin": "海口",
                "destination": "上海",
                "cost": item.get("flight_cost", 0),
                "hours": item.get("flight_hours", 0),
                "flight_no": item.get("flight_no"),
                "price_key": item.get("price_key"),
            },
            {
                "mode": "rail",
                "origin": "上海",
                "destination": "苏州",
                "cost": item.get("rail_cost", 0),
                "hours": item.get("rail_hours", 0),
            },
        ]
        add_row(rows, "direct_to_shanghai", "海口→上海→苏州", legs)

    # 2) haikou_to_zhanjiang_wuchuan：rail + transfer + flight + rail
    for item in data.get("haikou_to_zhanjiang_wuchuan", []):
        legs = [
            {
                "mode": "rail",
                "origin": "海口",
                "destination": "湛江",
                "cost": item.get("rail_cost", 0),
                "hours": item.get("rail_hours", 0),
                "notes": item.get("rail_note"),
            },
            {
                "mode": "taxi",
                "origin": "湛江站",
                "destination": "吴川机场",
                "cost": item.get("transfer_cost", 0),
                "hours": item.get("transfer_hours", 0),
            },
            {
                "mode": "flight",
                "origin": "湛江/吴川",
                "destination": "上海",
                "cost": item.get("flight_cost", 0),
                "hours": item.get("flight_hours", 0),
                "flight_no": item.get("flight_no"),
                "price_key": item.get("price_key"),
            },
            {
                "mode": "rail",
                "origin": "上海",
                "destination": "苏州",
                "cost": item.get("rail_to_suzhou_cost", 0),
                "hours": item.get("rail_to_suzhou_hours", 0),
            },
        ]
        add_row(rows, "haikou_to_zhanjiang_wuchuan", "海口→湛江→上海→苏州", legs)

    # 3) leave_hainan_then_transfer：two hops（这里数据里没写 origin/dest，只按文案汇总）
    for item in data.get("leave_hainan_then_transfer", []):
        legs = [
            {
                "mode": "flight",
                "origin": "海口",
                "destination": item.get("first_hop_to", ""),
                "cost": item.get("first_hop_cost", 0),
                "hours": item.get("first_hop_hours", 0),
                "price_key": item.get("first_hop_price_key"),
            },
            {
                "mode": "flight",
                "origin": item.get("first_hop_to", ""),
                "destination": item.get("transfer_city", ""),
                "cost": item.get("second_hop_cost", 0),
                "hours": item.get("second_hop_hours", 0),
                "price_key": item.get("second_hop_price_key"),
            },
        ]
        add_row(rows, "leave_hainan_then_transfer", f"海口→{item.get('first_hop_to','')}→{item.get('transfer_city','')}", legs)

    # 4) extra_strategies：已经是 legs 数组（最完整）
    for item in data.get("extra_strategies", []):
        legs = []
        for l in item.get("legs", []):
            legs.append(
                {
                    "mode": l.get("mode"),
                    "origin": l.get("origin"),
                    "destination": l.get("destination"),
                    "cost": l.get("cost", 0),
                    "hours": l.get("hours", 0),
                    "price_key": l.get("price_key"),
                    "notes": l.get("notes"),
                }
            )
        add_row(rows, "extra_strategies", item.get("name", "extra"), legs, notes="; ".join(item.get("risks", []) or []))

    return rows


def to_markdown_table(rows: List[Dict[str, Any]]) -> str:
    rows = sorted(rows, key=lambda r: (r["total_cost"], r["total_hours"]))
    header = "| 排名 | 方案 | 总价 | 总时长 | 细节 | 备注 |\n|---:|---|---:|---:|---|---|\n"
    lines = []
    for i, r in enumerate(rows, 1):
        lines.append(
            f"| {i} | {r['name']} | {money(r['total_cost'])} | {hours(r['total_hours'])} | {r['detail']} | {r['notes'] or ''} |"
        )
    return header + "\n".join(lines) + "\n"


def main():
    data = load()
    rows = summarize(data)
    md = to_markdown_table(rows)

    # 控制台输出（Actions 日志里可直接看到）
    print(md)

    # 同时写入文件，方便作为 artifact 下载
    Path("summary.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
