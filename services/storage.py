import threading
import json
import os


class UserStorage:
    _lock = threading.Lock()
    _targets = {}  # user_id: {'BTC': price, 'ETH': price}
    _trading_states = {}  # user_id: {'running': bool, 'order': {...}, 'position': {...}}
    _trading_file = os.path.join(os.path.dirname(__file__), 'trading_state.json')

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

    # Trading state persistence
    @classmethod
    def _load_trading_file(cls):
        try:
            if os.path.exists(cls._trading_file):
                with open(cls._trading_file, 'r', encoding='utf-8') as f:
                    cls._trading_states = json.load(f)
            else:
                cls._trading_states = {}
        except Exception:
            cls._trading_states = {}

    @classmethod
    def _save_trading_file(cls):
        try:
            tmp = cls._trading_file + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(cls._trading_states, f, ensure_ascii=False, indent=2)
            os.replace(tmp, cls._trading_file)
        except Exception:
            pass

    @classmethod
    def set_trading_state(cls, user_id: int, state: dict):
        with cls._lock:
            # only store serializable parts
            serializable = {
                'running': bool(state.get('running', False)),
                'order': state.get('order'),
                'position': state.get('position'),
            }
            cls._trading_states[str(user_id)] = serializable
            cls._save_trading_file()

    @classmethod
    def get_trading_state(cls, user_id: int):
        with cls._lock:
            if not cls._trading_states:
                cls._load_trading_file()
            return cls._trading_states.get(str(user_id))

    @classmethod
    def clear_trading_state(cls, user_id: int):
        with cls._lock:
            if not cls._trading_states:
                cls._load_trading_file()
            cls._trading_states.pop(str(user_id), None)
            cls._save_trading_file()

    @classmethod
    def list_trading_states(cls):
        with cls._lock:
            if not cls._trading_states:
                cls._load_trading_file()
            return cls._trading_states.copy()
