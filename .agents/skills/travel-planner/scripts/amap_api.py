#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""高德地图 API 封装：地理编码 / 天气 / 路径规划。

用法（PowerShell 示例）：
    python amap_api.py geocode "北京"
    python amap_api.py weather 110000
    python amap_api.py route "116.397428,39.90923" "116.322987,39.930636" walking
    python amap_api.py route "116.397428,39.90923" "116.322987,39.930636" driving

Key 来源：环境变量 AMAP_KEY，或 --key 参数。
无 Key 时脚本明确报错并退出码 2（调用方应降级到搜索，而非伪造数据）。
"""

import json
import os
import sys
import urllib.parse
import urllib.request

BASE = "https://restapi.amap.com/v3"


def get_key(args_key):
    key = args_key or os.environ.get("AMAP_KEY", "").strip()
    if not key:
        print(json.dumps({
            "error": "NO_AMAP_KEY",
            "message": "未配置高德 API Key。请设置环境变量 AMAP_KEY，或用 --key 传入。"
                       "获取方式：高德开放平台 console.amap.com 免费申请。",
        }, ensure_ascii=False))
        sys.exit(2)
    return key


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "travel-planner/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def geocode(key, address):
    url = (f"{BASE}/geocode/geo?key={key}&address={urllib.parse.quote(address)}")
    data = http_get(url)
    if data.get("status") != "1" or not data.get("geocodes"):
        print(json.dumps({"error": "GEOCODE_FAILED", "raw": data}, ensure_ascii=False))
        sys.exit(3)
    g = data["geocodes"][0]
    out = {
        "city": address,
        "formatted": g.get("formatted_address", ""),
        "adcode": g.get("adcode", ""),
        "location": g.get("location", ""),  # "lng,lat"
        "province": g.get("province", ""),
    }
    print(json.dumps(out, ensure_ascii=False))


def weather(key, city):
    url = (f"{BASE}/weather/weatherInfo?key={key}&city={urllib.parse.quote(city)}"
           f"&extensions=all")
    data = http_get(url)
    if data.get("status") != "1":
        print(json.dumps({"error": "WEATHER_FAILED", "raw": data}, ensure_ascii=False))
        sys.exit(3)
    lives = data.get("lives", [{}])[0]
    casts = data.get("forecasts", [{}])[0].get("casts", [])
    out = {
        "live": {
            "province": lives.get("province", ""),
            "city": lives.get("city", ""),
            "weather": lives.get("weather", ""),
            "temperature": lives.get("temperature", ""),
            "winddirection": lives.get("winddirection", ""),
            "windpower": lives.get("windpower", ""),
            "humidity": lives.get("humidity", ""),
            "reporttime": lives.get("reporttime", ""),
        },
        # 高德预报覆盖今日 + 未来 4 天；如需完整 7 天，用搜索补充
        "forecast_4days": [
            {
                "date": c.get("date", ""),
                "dayweather": c.get("dayweather", ""),
                "nightweather": c.get("nightweather", ""),
                "daytemp": c.get("daytemp", ""),
                "nighttemp": c.get("nighttemp", ""),
                "daywind": c.get("daywind", ""),
                "daypower": c.get("daypower", ""),
            }
            for c in casts
        ],
        "note": "高德预报覆盖今日+未来4天，完整7天请用天气网站搜索补充",
    }
    print(json.dumps(out, ensure_ascii=False))


def route(key, origin, destination, mode):
    if mode == "transit":
        url = f"{BASE}/direction/transit/integrated"
    else:
        url = f"{BASE}/direction/{mode}"
    params = {
        "key": key,
        "origin": origin,
        "destination": destination,
    }
    if mode in ("driving", "transit"):
        params["city"] = "010"  # 需要城市 adcode 时可替换
    url = url + "?" + urllib.parse.urlencode(params)
    data = http_get(url)
    if data.get("status") != "1":
        print(json.dumps({"error": "ROUTE_FAILED", "raw": data}, ensure_ascii=False))
        sys.exit(3)
    paths = data.get("route", {}).get("paths", [])
    if not paths:
        print(json.dumps({"error": "ROUTE_EMPTY", "raw": data}, ensure_ascii=False))
        sys.exit(3)
    p = paths[0]
    steps = []
    for s in p.get("steps", [])[:12]:
        steps.append({"instruction": s.get("instruction", ""), "distance": s.get("distance", "")})
    out = {
        "mode": mode,
        "distance_m": p.get("distance", ""),
        "duration_s": p.get("duration", ""),
        "duration_min": round(int(p.get("duration", 0)) / 60) if p.get("duration", "").isdigit() else None,
        "steps": steps,
    }
    print(json.dumps(out, ensure_ascii=False))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--key")]
    key_arg = None
    if "--key" in sys.argv:
        i = sys.argv.index("--key")
        key_arg = sys.argv[i + 1]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    key = get_key(key_arg)
    if cmd == "geocode":
        geocode(key, args[1])
    elif cmd == "weather":
        weather(key, args[1])
    elif cmd == "route":
        if len(args) < 4:
            print("用法: route <origin> <destination> <walking|driving|transit>")
            sys.exit(1)
        route(key, args[1], args[2], args[3])
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main()
