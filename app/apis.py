"""
外部資料 API 封裝：股價、新聞、天氣
三個都刻意選用「不需要申請 API 金鑰」的資料源，避免每加一個功能就要再走一次申請流程。
"""
import time
import logging
import xml.etree.ElementTree as ET
import httpx

logger = logging.getLogger("line-bot.apis")

# ---------------------------------------------------------------------------
# 股價：證交所(TWSE) OpenAPI，每日收盤資訊（非即時，約收盤後更新）
# 上市(TWSE)查不到再試上櫃(TPEx)
# ---------------------------------------------------------------------------
_stock_cache = {"tse": None, "tpex": None, "ts": 0}
_STOCK_CACHE_TTL = 300  # 秒，避免每次查詢都重抓全市場資料


async def _load_stock_data():
    now = time.time()
    if _stock_cache["tse"] is not None and now - _stock_cache["ts"] < _STOCK_CACHE_TTL:
        return

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            tse_resp = await client.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")
            tse_resp.raise_for_status()
            _stock_cache["tse"] = {row["Code"]: row for row in tse_resp.json()}
        except Exception:
            logger.exception("抓取 TWSE 上市股價資料失敗")
            _stock_cache["tse"] = {}

        try:
            tpex_resp = await client.get(
                "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
            )
            tpex_resp.raise_for_status()
            data = tpex_resp.json()
            # TPEx 欄位名稱跟 TWSE 不同，這裡統一轉成跟 TWSE 一致的 key 方便後面共用
            _stock_cache["tpex"] = {
                row.get("SecuritiesCompanyCode", row.get("Code", "")): row for row in data
            }
        except Exception:
            logger.exception("抓取 TPEx 上櫃股價資料失敗")
            _stock_cache["tpex"] = {}

    _stock_cache["ts"] = now


async def get_stock_quote(code: str) -> str:
    code = code.strip()
    await _load_stock_data()

    row = _stock_cache["tse"].get(code)
    if row:
        name = row.get("Name", code)
        close = row.get("ClosingPrice", "N/A")
        change = row.get("Change", "N/A")
        open_ = row.get("OpeningPrice", "N/A")
        high = row.get("HighestPrice", "N/A")
        low = row.get("LowestPrice", "N/A")
        volume = row.get("TradeVolume", "N/A")
        return (
            f"📈 {name}（{code}）上市\n"
            f"收盤：{close}　漲跌：{change}\n"
            f"開：{open_}　高：{high}　低：{low}\n"
            f"成交股數：{volume}\n"
            f"（資料來源：證交所 OpenAPI，非即時，為最近一個交易日收盤資訊）"
        )

    row = _stock_cache["tpex"].get(code)
    if row:
        name = row.get("CompanyName", row.get("Name", code))
        close = row.get("Close", row.get("ClosingPrice", "N/A"))
        change = row.get("Change", "N/A")
        return (
            f"📈 {name}（{code}）上櫃\n"
            f"收盤：{close}　漲跌：{change}\n"
            f"（資料來源：櫃買中心 OpenAPI，非即時，為最近一個交易日收盤資訊）"
        )

    return f"查不到代號 {code} 的股價資料，請確認代號是否正確（僅支援上市櫃股票）。"


# ---------------------------------------------------------------------------
# 新聞：Google News RSS，按關鍵字搜尋，不需要 API key
# ---------------------------------------------------------------------------
async def get_news(query: str, limit: int = 5) -> str:
    query = query.strip()
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(
                "https://news.google.com/rss/search",
                params={"q": query, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"},
            )
            resp.raise_for_status()
        except Exception:
            logger.exception("抓取新聞失敗")
            return "抱歉，新聞查詢暫時失敗，請稍後再試。"

    try:
        root = ET.fromstring(resp.text)
        items = root.findall("./channel/item")[:limit]
        if not items:
            return f"沒有找到跟「{query}」相關的新聞。"

        lines = [f"📰「{query}」相關新聞："]
        for i, item in enumerate(items, 1):
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            lines.append(f"{i}. {title}\n{link}")
        return "\n\n".join(lines)
    except ET.ParseError:
        logger.exception("解析新聞 RSS 失敗")
        return "抱歉，新聞查詢暫時失敗，請稍後再試。"


# ---------------------------------------------------------------------------
# 天氣：Open-Meteo，完全免費不用註冊
# ---------------------------------------------------------------------------
_WEATHER_CODE_MAP = {
    0: "晴朗", 1: "大致晴朗", 2: "多雲", 3: "陰天",
    45: "有霧", 48: "霧淞",
    51: "毛毛雨(小)", 53: "毛毛雨(中)", 55: "毛毛雨(大)",
    61: "雨(小)", 63: "雨(中)", 65: "雨(大)",
    66: "凍雨(小)", 67: "凍雨(大)",
    71: "雪(小)", 73: "雪(中)", 75: "雪(大)",
    80: "陣雨(小)", 81: "陣雨(中)", 82: "陣雨(大)",
    95: "雷雨", 96: "雷雨挾冰雹", 99: "強雷雨挾冰雹",
}


async def get_weather(city: str) -> str:
    city = city.strip()
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            geo_resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "zh", "format": "json"},
            )
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()
        except Exception:
            logger.exception("地點查詢失敗")
            return "抱歉，天氣查詢暫時失敗，請稍後再試。"

        results = geo_data.get("results")
        if not results:
            return f"找不到「{city}」這個地點，請確認地名是否正確（建議用中文城市名，例如「台南」「東京」）。"

        place = results[0]
        lat, lon = place["latitude"], place["longitude"]
        place_name = place.get("name", city)
        country = place.get("country", "")

        try:
            weather_resp = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current_weather": "true",
                    "daily": "temperature_2m_max,temperature_2m_min",
                    "timezone": "auto",
                },
            )
            weather_resp.raise_for_status()
            w = weather_resp.json()
        except Exception:
            logger.exception("天氣查詢失敗")
            return "抱歉，天氣查詢暫時失敗，請稍後再試。"

    current = w.get("current_weather", {})
    temp = current.get("temperature", "N/A")
    windspeed = current.get("windspeed", "N/A")
    code = current.get("weathercode")
    desc = _WEATHER_CODE_MAP.get(code, "未知天況")

    daily = w.get("daily", {})
    try:
        today_max = daily["temperature_2m_max"][0]
        today_min = daily["temperature_2m_min"][0]
        range_line = f"今日高低溫：{today_min}°C ~ {today_max}°C\n"
    except (KeyError, IndexError):
        range_line = ""

    return (
        f"🌤 {place_name}{('，' + country) if country else ''}\n"
        f"目前：{temp}°C，{desc}\n"
        f"{range_line}"
        f"風速：{windspeed} km/h\n"
        f"（資料來源：Open-Meteo）"
    )
