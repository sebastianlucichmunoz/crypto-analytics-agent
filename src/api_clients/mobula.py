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
        
        # Coincidencia certera: evalúa si el query coincide con el 'id' técnico o con el 'symbol'
        exact = [
            x for x in rows 
            if str(x.get("id", "")).lower() == query or str(x.get("symbol", "")).lower() == query
        ]
        
        if name:
            by_name = [x for x in rows if str(x.get("name", "")).lower() == str(name).lower()]
            if by_name:
                return by_name[0]
                
        # Si encuentra coincidencia exacta la devuelve; si no, toma el primer resultado de la lista de búsqueda
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
                # Asegurar que se inyecte el ID para que history.py lo reconozca
                if isinstance(data, dict):
                    data["id"] = asset_id
                    out.append(data)
                else:
                    out.append({"id": asset_id, "prices": []})
                
                time.sleep(3.0)  # Pausa para respetar el límite de CoinGecko
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
                # CoinGecko devuelve una lista de listas: [[timestamp, open, high, low, close], ...]
                out.append({
                    "id": asset_id,
                    "data": data if isinstance(data, list) else []
                })
                time.sleep(1.2) # Pausa para respetar el límite gratuito de la API
            except Exception:
                out.append({"id": asset_id, "data": []})
        return out




#Funciona bien
# from src.config import settings, require
# from src.http_client import HttpClient

# def batches(items, size=10):
#     for i in range(0, len(items), size):
#         yield items[i:i+size]

# class MobulaClient:
#     def __init__(self):
#         require("coingecko_api_key")
#         self.http = HttpClient()
#         self.base_url = "https://api.coingecko.com/api/v3"
#         self.headers = {
#             "Accept": "application/json",
#             "Content-Type": "application/json",
#             "x-cg-demo-api-key": settings.coingecko_api_key,
#         }

#     def search_asset(self, symbol, name=None):
#         query = str(symbol).lower()
#         r = self.http.request(
#             "GET",
#             f"{self.base_url}/search",
#             headers=self.headers,
#             params={"query": query},
#         )
#         data = r.json().get("coins", []) or []
#         rows = []
#         for x in data:
#             rows.append({
#                 "id": x.get("id"),
#                 "symbol": x.get("symbol", "").upper(),
#                 "name": x.get("name"),
#                 "market_cap_rank": x.get("market_cap_rank")
#             })
        
#         # Coincidencia certera: evalúa si el query coincide con el 'id' técnico o con el 'symbol'
#         exact = [
#             x for x in rows 
#             if str(x.get("id", "")).lower() == query or str(x.get("symbol", "")).lower() == query
#         ]
        
#         if name:
#             by_name = [x for x in rows if str(x.get("name", "")).lower() == str(name).lower()]
#             if by_name:
#                 return by_name[0]
                
#         # Si encuentra coincidencia exacta la devuelve; si no, toma el primer resultado de la lista de búsqueda
#         return exact[0] if exact else (rows[0] if rows else None)

#     def asset_details(self, asset_id):
#         r = self.http.request(
#             "GET", f"{self.base_url}/coins/{asset_id}",
#             headers=self.headers,
#         )
#         return r.json() or {}

#     def asset_details_batch(self, ids):
#         out = []
#         for asset_id in ids:
#             try:
#                 res = self.asset_details(asset_id)
#                 if res:
#                     out.append(res)
#             except Exception:
#                 pass
#         return out
    
#     def price_history_batch(self, payload):
#         out = []
#         for item in (payload if isinstance(payload, list) else [payload]):
#             asset_id = str(item.get("id") or item.get("asset") or "bitcoin")
#             days = item.get("days", "max")
#             try:
#                 r = self.http.request(
#                     "GET", f"{self.base_url}/coins/{asset_id}/market_chart",
#                     headers=self.headers,
#                     params={"vs_currency": "usd", "days": days}
#                 )
#                 data = r.json()
#                 if isinstance(data, dict):
#                     data["id"] = asset_id
#                 out.append(data)
#             except Exception:
#                 out.append({})
#         return out

#     def token_ohlcv_batch(self, payload):
#         out = []
#         for item in (payload if isinstance(payload, list) else [payload]):
#             asset_id = str(item.get("id") or item.get("asset") or "bitcoin")
#             days = item.get("days", "14")
#             try:
#                 r = self.http.request(
#                     "GET", f"{self.base_url}/coins/{asset_id}/ohlc",
#                     headers=self.headers,
#                     params={"vs_currency": "usd", "days": days}
#                 )
#                 data = r.json()
#                 out.append({"id": asset_id, "data": data if isinstance(data, list) else []})
#             except Exception:
#                 out.append({"id": asset_id, "data": []})
#         return out


















# from src.config import settings, require
# from src.http_client import HttpClient

# def batches(items, size=10):
#     for i in range(0, len(items), size):
#         yield items[i:i+size]

# class MobulaClient:
#     def __init__(self):
#         require("mobula_api_key")
#         self.http = HttpClient()
#         self.headers = {
#             "Authorization": settings.mobula_api_key,
#             "Accept": "application/json",
#             "Content-Type": "application/json",
#         }

#     def search_asset(self, symbol, name=None):
#         r = self.http.request(
#             "GET",
#             f"{settings.mobula_base_url}/2/fast-search",
#             headers=self.headers,
#             params={"input": f'"{symbol}"', "type": "assets", "sortBy": "marketCap", "limit": 10},
#         )
#         rows = r.json().get("data", []) or []
#         exact = [x for x in rows if str(x.get("symbol", "")).upper() == str(symbol).upper()]
#         if name:
#             by_name = [x for x in exact if str(x.get("name", "")).lower() == str(name).lower()]
#             if by_name:
#                 return by_name[0]
#         return exact[0] if exact else (rows[0] if rows else None)

#     def asset_details(self, asset_id):
#         r = self.http.request(
#             "GET", f"{settings.mobula_base_url}/2/asset/details",
#             headers=self.headers, params={"id": int(asset_id), "tokensLimit": 10},
#         )
#         return r.json().get("data", {}) or {}

#     def asset_details_batch(self, ids):
#         out = []
#         for batch in batches(ids):
#             r = self.http.request(
#                 "POST", f"{settings.mobula_base_url}/2/asset/details",
#                 headers=self.headers,
#                 json=[{"id": int(x), "tokensLimit": 10} for x in batch],
#             )
#             payload = r.json()
#             out.extend(payload.get("payload", payload.get("data", [])) or [])
#         return out

#     def price_history_batch(self, payload):
#         out = []
#         for batch in batches(payload):
#             r = self.http.request(
#                 "POST", f"{settings.mobula_base_url}/2/asset/price-history",
#                 headers=self.headers, json=batch,
#             )
#             data = r.json().get("data", [])
#             out.extend(data if isinstance(data, list) else [data])
#         return out

#     def token_ohlcv_batch(self, payload):
#         out = []
#         for batch in batches(payload):
#             r = self.http.request(
#                 "POST", f"{settings.mobula_base_url}/2/token/ohlcv-history",
#                 headers=self.headers, json=batch,
#             )
#             data = r.json().get("data", [])
#             out.extend(data if isinstance(data, list) else [data])
#         return out
