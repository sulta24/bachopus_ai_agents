#!/usr/bin/env python3
"""
datadog_fetch.py
Запрашивает метрики и логи из Datadog за выбранный период.
"""

import argparse
import requests
import json
from datetime import datetime, timedelta

# ==== Настройки ====
DD_API_KEY = "3cb244343cf0b67a853fab8dd26adace"
DD_APP_KEY = "1879f3e74ab7e870e5fb9e1558f4427633cb1bcc"
DATADOG_SITE = "datadoghq.eu"  # если у тебя global — поменяй на datadoghq.com

API_BASE = f"https://api.{DATADOG_SITE}"
HEADERS = {
    "DD-API-KEY": DD_API_KEY,
    "DD-APPLICATION-KEY": DD_APP_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# ==== Утилиты ====
def epoch_seconds(dt: datetime) -> int:
    return int(dt.timestamp())

def print_json(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))

# ==== Метрики ====
def query_metrics(query: str, start_dt: datetime, end_dt: datetime):
    """Запрашивает метрики по API v1/query"""
    url = f"{API_BASE}/api/v1/query"
    params = {
        "from": epoch_seconds(start_dt),
        "to": epoch_seconds(end_dt),
        "query": query,
    }
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Metrics query failed: {resp.status_code} {resp.text}")
    return resp.json()

# ==== Логи ====
def fetch_logs(query: str, start_dt: datetime, end_dt: datetime, limit_per_page: int = 10):
    """Запрашивает логи по API v2/logs/events/search (аналог твоего curl)"""
    url = f"{API_BASE}/api/v2/logs/events/search"
    body = {
        "filter": {
            "query": query,
            "from": start_dt.isoformat() + "Z",
            "to": end_dt.isoformat() + "Z",
        },
        "page": {"limit": limit_per_page},
        "sort": "timestamp"
    }

    resp = requests.post(url, headers=HEADERS, json=body, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Logs query failed: {resp.status_code} {resp.text}")
    return resp.json()

# ==== Основной код ====
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Datadog metrics and logs for a given time range.")
    parser.add_argument("--minutes", type=int, help="Период в минутах", default=15)
    parser.add_argument("--hours", type=int, help="Период в часах", default=0)
    args = parser.parse_args()

    delta = timedelta(minutes=args.minutes, hours=args.hours)
    end = datetime.utcnow()
    start = end - delta

    print(f"\n=== Запрос данных Datadog c {start} по {end} (UTC) ===")

    # ---- Метрики ----
    try:
        print("\n=== METRICS ===")
        metrics_query = "avg:system.cpu.user{*}"  # можешь поменять под свой хост
        metrics = query_metrics(metrics_query, start, end)
        print_json(metrics)
    except Exception as e:
        print("Ошибка при запросе метрик:", e)

    # ---- Логи ----
    try:
        print("\n=== LOGS ===")
        logs_query = "service:auarai AND env:prod"  # как в твоем curl
        logs_data = fetch_logs(logs_query, start, end, limit_per_page=10)
        print_json(logs_data)
    except Exception as e:
        print("Ошибка при запросе логов:", e)
