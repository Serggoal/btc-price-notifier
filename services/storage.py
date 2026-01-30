import threading


class UserStorage:
    _lock = threading.Lock()
    _targets = {}  # user_id: {'BTC': price, 'ETH': price}

    @classmethod
    def set_target(cls, user_id: int, price: float, coin: str = "BTC"):
        with cls._lock:
            if user_id not in cls._targets:
                cls._targets[user_id] = {}
            cls._targets[user_id][coin] = price

    @classmethod
    def get_target(cls, user_id: int, coin: str = "BTC"):
        with cls._lock:
            return cls._targets.get(user_id, {}).get(coin)

    @classmethod
    def clear_target(cls, user_id: int, coin: str = "BTC"):
        with cls._lock:
            if user_id in cls._targets and coin in cls._targets[user_id]:
                del cls._targets[user_id][coin]
