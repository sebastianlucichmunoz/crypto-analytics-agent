import time
from src.config import settings, require
from src.http_client import HttpClient

def batches(items, size=10):
    for i in range(0, len(items), size):
        yield items[i:i+size]

class MobulaClient:
    def __init__(self):
        require("coingecko_api_key")
        self.http = HttpClient()
        self.base_url = "https://api.coingecko.com/api/v3"
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-cg-demo-api-key": settings.coingecko_api_key,
        }

    def search_asset(self, symbol, name=None):
        query = str(symbol).lower()
        r = self.http.request(
            "GET",
            f"{self.base_url}/search",
            headers=self.headers,
            params={"query": query},
        )
        data = r.json().get("coins", []) or []
        rows = []
        for x in data:
            rows.append({
                "id": x.get("id"),
                "symbol": x.get("symbol", "").upper(),
                "name": x.get("name"),
                "market_cap_rank": x.get("market_cap_rank")
            })
    
        exact = [
            x for x in rows 
            if str(x.get("id", "")).lower() == query or str(x.get("symbol", "")).lower() == query
        ]
        
        if name:
            by_name = [x for x in rows if str(x.get("name", "")).lower() == str(name).lower()]
            if by_name:
                return by_name[0]
   
        return exact[0] if exact else (rows[0] if rows else None)

    def asset_details(self, asset_id):
        r = self.http.request(
            "GET", f"{self.base_url}/coins/{asset_id}",
            headers=self.headers,
        )
        return r.json() or {}

    def asset_details_batch(self, ids):
        out = []
        for asset_id in ids:
            try:
                res = self.asset_details(asset_id)
                if res:
                    out.append(res)
            except Exception:
                pass
        return out

    def price_history_batch(self, payload):
        out = []
        for item in (payload if isinstance(payload, list) else [payload]):
            asset_id = str(item.get("id") or item.get("asset") or "bitcoin")
            days = item.get("days", "max")
            try:
                r = self.http.request(
                    "GET", f"{self.base_url}/coins/{asset_id}/market_chart",
                    headers=self.headers,
                    params={"vs_currency": "usd", "days": days}
                )
                data = r.json()
                if isinstance(data, dict):
                    data["id"] = asset_id
                    out.append(data)
                else:
                    out.append({"id": asset_id, "prices": []})
   
            except Exception:
                out.append({"id": asset_id, "prices": []})
        return out

    def token_ohlcv_batch(self, payload):
        out = []
        for item in (payload if isinstance(payload, list) else [payload]):
            asset_id = str(item.get("id") or item.get("asset") or "bitcoin")
            days = item.get("days", "14")
            try:
                r = self.http.request(
                    "GET", f"{self.base_url}/coins/{asset_id}/ohlc",
                    headers=self.headers,
                    params={"vs_currency": "usd", "days": days}
                )
                data = r.json()
                out.append({
                    "id": asset_id,
                    "data": data if isinstance(data, list) else []
                })
            except Exception:
                out.append({"id": asset_id, "data": []})
        return out
