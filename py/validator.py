"""输入校验工具。"""
import re

from . import config


def normalize_icao(value):
    """标准化 ICAO 机场代码（4 位纯字母，不允许数字/符号），非法返回 None。"""
    if not value or not isinstance(value, str):
        return None
    code = value.strip().upper()
    return code if re.fullmatch(r'[A-Z]{4}', code) else None


def is_valid_callsign(value):
    """校验呼号（2-12 位字母数字，大小写不敏感）。"""
    if not value or not isinstance(value, str):
        return False
    return bool(re.fullmatch(r'[a-zA-Z0-9]{2,12}', value.strip()))


def truncate(s, max_len=1000):
    """截断字符串并添加省略号。"""
    if not s:
        return ''
    return s if len(s) <= max_len else s[:max_len] + '…'


def split_icao_list(input_str, max_items=5):
    """安全拆分逗号/空白分隔的 ICAO 列表。"""
    if not input_str:
        return []
    items = [x for x in re.split(r'[,，\s]+', input_str) if x][:max_items]
    return [x for x in (normalize_icao(i) for i in items) if x]


def is_allowed_group(group_id):
    """是否为允许的群。"""
    return str(group_id) in config.allowed_group_ids()
