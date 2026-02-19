#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
OFFERS_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"


@dataclass(frozen=True)
class RouteQuery:
    key: str
    origin: str
    destination: str
    # 兼容两种：1) 指定日期 departure_date；2) 用 offset 计算日期
    departure_date: str | None
    date_offset_days: int


@dataclass(frozen=True)
class PriceResult:
    key: str
    amount: float
    currency: str


class AmadeusClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    def _request_json(self, req: Request) -> dict[str, Any]:
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_access_token(self) -> str:
        payload = urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        ).encode("utf-8")
        req = Request(TOKEN_URL, data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        data = self._request_json(req)
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"无法获取 access_token: {data}")
        return token

    def get_lowest_oneway_price(
        self,
        *,
        token: str,
        origin: str,
        destination: str,
        departure_date: str,
        adults: int = 1,
        max_results: int = 20,
    ) -> tuple[float, str]:
        query = urlencode(
            {
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date,
                "adults": adults,
                "nonStop": "false",
                "max": max_results,
                "currencyCode": "CNY",
            }
        )
        req = Request(f"{OFFERS_URL}?{query}", method="GET")
        req.add_header("Authorization", f"Bearer {token}")
        data = self._request_json(req)

        offers = data.get("data", [])
        if not offers:
            raise RuntimeError(f"未查询到报价: {origin}->{destination} {departure_date}")

        prices = []
        for offer in offers:
            p = offer.get("price", {})
            total = p.get("total")
            cur = p.get("currency", "CNY")
            if total is None:
                continue
            prices.append((float(total), cur))

        if not prices:
            raise RuntimeError(f"报价结构异常: {origin}->{destination} {departure_date}")

        return min(prices, key=lambda x: x[0])


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def resolve_queries(config: dict[str, Any]) -> list[RouteQuery]:
    queries: list[RouteQuery] = []
    for item in config.get("routes", []):
        queries.append(
            RouteQuery(
                key=item["key"],
                origin=item["origin"],
                destination=item["destination"],
                departure_date=item.get("departure_date"),
                date_offset_days=int(item.get("date_offset_days", 3)),
            )
        )
    return queries


def build_departure_date(q: RouteQuery) -> str:
    if q.departure_date:
        return q.departure_date
    return (date.today() + timedelta(days=q.date_offset_days)).isoformat()


def fetch_prices(client: AmadeusClient, queries: list[RouteQuery]) -> list[PriceResult]:
    token = client.get_access_token()
    results: list[PriceResult] = []
    for q in queries:
        dep = build_departure_date(q)
        amount, currency = client.get_lowest_oneway_price(
            token=token,
            origin=q.origin,
            destination=q.destination,
            departure_date=dep,
        )
        results.append(PriceResult(key=q.key, amount=amount, currency=currency))
    return results


def apply_price_updates(dataset: dict[str, Any], results: list[PriceResult]) -> dict[str, Any]:
    by_key = {r.key: r for r in results}

    for item in dataset.get("direct_to_shanghai", []):
        key = item.get("price_key")
        if key in by_key:
            item["flight_cost"] = round(by_key[key].amount, 2)

    for item in dataset.get("haikou_to_zhanjiang_wuchuan", []):
        key = item.get("price_key")
        if key in by_key:
            item["flight_cost"] = round(by_key[key].amount, 2)

    for item in dataset.get("leave_hainan_then_transfer", []):
        k1 = item.get("first_hop_price_key")
        k2 = item.get("second_hop_price_key")
        if k1 in by_key:
            item["first_hop_cost"] = round(by_key[k1].amount, 2)
        if k2 in by_key:
            item["second_hop_cost"] = round(by_key[k2].amount, 2)

    for item in dataset.get("extra_strategies", []):
        for leg in item.get("legs", []):
            key = leg.get("price_key")
            if key in by_key and leg.get("mode") == "flight":
                leg["cost"] = round(by_key[key].amount, 2)

    return dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取实时机票价格并更新 JSON")
    parser.add_argument("--config", default="data/routes_config.json", help="航线抓取配置")
    parser.add_argument("--data", default="data/sample_options.json", help="要更新的方案 JSON")
    parser.add_argument("--dry-run", action="store_true", help="仅打印更新结果，不写回文件")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    client_id = os.getenv("AMADEUS_CLIENT_ID")
    client_secret = os.getenv("AMADEUS_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("请先设置环境变量 AMADEUS_CLIENT_ID 和 AMADEUS_CLIENT_SECRET")

    config = load_json(Path(args.config))
    dataset = load_json(Path(args.data))

    client = AmadeusClient(client_id, client_secret)
    queries = resolve_queries(config)
    results = fetch_prices(client, queries)

    updated = apply_price_updates(dataset, results)

    if args.dry_run:
        print(json.dumps(updated, ensure_ascii=False, indent=2))
    else:
        save_json(Path(args.data), updated)
        print(f"已更新 {args.data}，共写入 {len(results)} 条实时票价")


if __name__ == "__main__":
    main()
