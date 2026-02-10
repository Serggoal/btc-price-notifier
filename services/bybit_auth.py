import time
import hmac
import hashlib
import json
import logging
import httpx
from config import BYBIT_BASE_URL, BYBIT_API_KEY, BYBIT_API_SECRET


async def signed_request(method: str, path: str, params: dict = None, body: dict = None, recv_window: int = 5000):
    """Send signed request to Bybit v5 private API. Returns parsed JSON.

    NOTE: This implements the common HMAC-SHA256 signing pattern used by Bybit v5.
    Ensure `BYBIT_API_KEY` and `BYBIT_API_SECRET` are set in .env.
    """
    if BYBIT_API_KEY is None or BYBIT_API_SECRET is None:
        raise RuntimeError('Bybit API credentials not configured')

    ts = str(int(time.time() * 1000))
    method_upper = method.upper()

    # Build query string (for GET) or body string (for POST/others)
    qry = ''
    if params:
        from urllib.parse import urlencode
        items = []
        for k in sorted(params.keys()):
            v = params[k]
            if isinstance(v, (list, tuple)):
                for vv in v:
                    items.append((k, vv))
            else:
                items.append((k, v))
        qry = urlencode(items, doseq=True)

    body_str = json.dumps(body, separators=(',', ':')) if body else ''

    # Per Bybit V5 examples: signature = HMAC_SHA256(secret, timestamp + apiKey + recvWindow + (queryString | bodyJson))
    payload_for_sign = ''
    if method_upper == 'GET':
        payload_for_sign = qry
    else:
        payload_for_sign = body_str

    to_sign = ts + (BYBIT_API_KEY or '') + str(recv_window) + payload_for_sign
    signature = hmac.new(BYBIT_API_SECRET.encode(), to_sign.encode(), hashlib.sha256).hexdigest()

    headers = {
        'Content-Type': 'application/json',
        'X-BAPI-API-KEY': BYBIT_API_KEY,
        'X-BAPI-TIMESTAMP': ts,
        'X-BAPI-SIGN': signature,
        'X-BAPI-RECV-WINDOW': str(recv_window),
        'X-BAPI-SIGN-TYPE': '2',
    }

    url = BYBIT_BASE_URL + path + (('?' + qry) if (method_upper == 'GET' and qry) else '')
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.request(method_upper, url, headers=headers, content=body_str if body_str else None)
        try:
            resp.raise_for_status()
        except Exception as e:
            logging.error(f'Bybit auth request error {resp.status_code} {resp.text}')
            raise
        return resp.json()
