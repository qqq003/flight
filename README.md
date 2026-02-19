# 海口 → 苏州 最低成本出行方案工具

这个仓库提供一个可复用的命令行工具，用于对比多种“航班 + 地面接驳”组合并按总成本排序。

## 已覆盖策略

1. 海口直飞上海，再高铁到苏州。  
2. 海口先到湛江，再去吴川机场飞上海。  
3. 先离开海南（不明显反方向）后转飞/转高铁。  
4. 经上海去境外的“甩尾”思路（仅做价格评估，含风险提示）。  
5. 先飞免签国家再回国。  
6. 补充策略：飞无锡/南京/杭州/宁波等周边城市后进苏州。  

## 快速开始

```bash
python3 planner.py --data data/sample_options.json --top 5
```

## 实时机票抓取并更新 JSON

新增脚本：`scripts/update_prices.py`（基于 Amadeus API）。

### 1) 配置 API 密钥（环境变量）

```bash
export AMADEUS_CLIENT_ID="你的_client_id"
export AMADEUS_CLIENT_SECRET="你的_client_secret"
```

### 2) 先 dry-run 看更新结果

```bash
python3 scripts/update_prices.py --config data/routes_config.json --data data/sample_options.json --dry-run
```

### 3) 正式写回 JSON

```bash
python3 scripts/update_prices.py --config data/routes_config.json --data data/sample_options.json
```

### 4) 定时更新（cron，每 2 小时）

```bash
crontab -e
```

加入（示例）：

```cron
0 */2 * * * cd /workspace/flight && /usr/bin/env bash -lc 'source ~/.bashrc && python3 scripts/update_prices.py --config data/routes_config.json --data data/sample_options.json >> logs/price_update.log 2>&1'
```

> 建议先执行 `mkdir -p /workspace/flight/logs`。

## 数据格式

你后续只需维护一个 JSON 文件，程序会自动计算每条路线总价和总耗时。

- `direct_to_shanghai`: 直飞上海方案列表
- `haikou_to_zhanjiang_wuchuan`: 铁路 + 吴川机场方案
- `leave_hainan_then_transfer`: 先离岛再转运方案
- `hidden_city_like`: 甩尾类方案（会自动附风险）
- `visa_free_outbound_then_back`: 出境再回国方案
- `extra_strategies`: 你自定义的任意新增方案

若某个航段需要自动更新票价，请在对应段加入 `price_key`，并在 `data/routes_config.json` 中配置该 key 的 IATA 航线。

## 风险与合规提示

- “甩尾”可能违反航司规则，且托运行李通常不可中途取出。
- 出境再回国方案受政策、税费和行李规则影响较大。

