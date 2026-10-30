"""简单的内存限流器（用户级/全局级冷却）。"""
import math
import time

_user_buckets = {}
_global_buckets = {}


def check_user_cooldown(key, cooldown):
    """检查用户冷却。返回剩余秒数（int），None 表示允许。"""
    return _check(_user_buckets, key, cooldown)


def check_global_cooldown(key, cooldown):
    """检查全局冷却。返回剩余秒数（int），None 表示允许。"""
    return _check(_global_buckets, key, cooldown)


def _check(buckets, key, cooldown):
    now = time.time()
    entry = buckets.get(key)
    if entry is not None:
        remaining = cooldown - (now - entry)
        if remaining > 0:
            return math.ceil(remaining)
    buckets[key] = now
    return None


def clean_cooldowns():
    """清理超过 5 分钟的过期记录。"""
    now = time.time()
    for buckets in (_user_buckets, _global_buckets):
        for key, ts in list(buckets.items()):
            if now - ts > 300:
                buckets.pop(key, None)
