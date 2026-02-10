import logging
from typing import Optional
from services.bybit_auth import signed_request
from decimal import Decimal, ROUND_DOWN, getcontext


def normalize_qty(qty: float, min_size: float = 0.01, step: float = 0.001):
    """Round down `qty` to nearest `step` using Decimal arithmetic.

    Returns tuple (rounded_qty: float, ok: bool) where ok is False when
    rounded_qty < min_size.
    """
    getcontext().prec = 18
    qtyD = Decimal(str(qty))
    stepD = Decimal(str(step))
    # number of steps (floor)
    steps = (qtyD / stepD).to_integral_value(rounding=ROUND_DOWN)
    rounded = (steps * stepD).quantize(stepD)
    if rounded < Decimal(str(min_size)):
        return float(rounded), False
    return float(rounded), True


async def get_balance(coin: Optional[str] = None):
    # Bybit v5 endpoint for wallet balance: /v5/account/wallet-balance
    path = '/v5/account/wallet-balance'
    # Bybit requires accountType for this endpoint; default to UNIFIED
    params = {'accountType': 'UNIFIED'}
    res = await signed_request('GET', path, params=params)
    # return full result; caller can filter by coin
    return res


async def get_open_orders(symbol: Optional[str] = None):
    # Bybit v5 endpoint for active orders: /v5/order/realtime
    path = '/v5/order/realtime'
    params = {'symbol': symbol} if symbol else None
    res = await signed_request('GET', path, params=params)
    return res


async def create_order(symbol: str, side: str, qty: float, order_type: str = 'Market', price: Optional[float] = None, time_in_force: str = 'GTC', category: str = 'linear'):
    # v5 order create: /v5/order/create
    path = '/v5/order/create'
    # Bybit expects side as 'Buy' or 'Sell' (case-sensitive in V5 examples)
    side_normalized = side.capitalize() if isinstance(side, str) else side
    body = {
        'category': category,
        'symbol': symbol,
        'side': side_normalized,
        'orderType': order_type,
        'qty': str(qty),
        'timeInForce': time_in_force,
        'reduceOnly': False,
        'closeOnTrigger': False,
    }
    if price is not None:
        body['price'] = str(price)
    res = await signed_request('POST', path, body=body)
    return res


async def cancel_order(symbol: str, order_id: str):
    path = '/v5/order/cancel'
    body = {'symbol': symbol, 'orderLinkId': order_id}
    res = await signed_request('POST', path, body=body)
    return res
