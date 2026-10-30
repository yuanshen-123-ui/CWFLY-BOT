"""机场查询服务 - 使用 OurAirports 官方数据，从 CSV 加载到内存。"""
import asyncio
import csv
import time
from pathlib import Path

from .. import config
from . import http

OUR_AIRPORTS_URL = (
    'https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv')
CACHE_FILE = Path(config.airport_cache_file())

_airport_map = None
_last_fetch = 0


def _ensure_cache_dir():
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


async def _download_airport_data():
    _ensure_cache_dir()
    resp = await http.http_get(OUR_AIRPORTS_URL, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f'HTTP {resp.status_code}')
    text = resp.text
    CACHE_FILE.write_text(text, encoding='utf-8')
    global _last_fetch
    _last_fetch = time.time()
    return text


async def load_airports():
    """读取机场数据，如需则下载更新。"""
    global _airport_map, _last_fetch
    if _airport_map is not None and time.time() - _last_fetch < 86400:
        return

    if not CACHE_FILE.exists():
        try:
            await _download_airport_data()
        except Exception:
            _airport_map = {}
            return
    else:
        _last_fetch = time.time()
        try:
            # 超过 24 小时则后台更新
            if time.time() - CACHE_FILE.stat().st_mtime > 86400:
                asyncio.ensure_future(_download_airport_data())
        except Exception:
            pass

    try:
        with CACHE_FILE.open(encoding='utf-8', errors='replace', newline='') as f:
            reader = csv.DictReader(f)
            _airport_map = {}
            for row in reader:
                ident = (row.get('ident') or '').upper()
                if ident and row.get('type') and row.get('type') != 'closed':
                    _airport_map[ident] = row
    except Exception:
        if _airport_map is None:
            _airport_map = {}


_TYPE_MAP = {
    'large_airport': '大型机场',
    'medium_airport': '中型机场',
    'small_airport': '小型机场',
    'heliport': '直升机场',
    'seaplane_base': '水上飞机基地',
    'closed': '已关闭',
}

_COUNTRY_NAMES = {
    'CN': '中国', 'US': '美国', 'GB': '英国', 'JP': '日本',
    'KR': '韩国', 'DE': '德国', 'FR': '法国', 'AU': '澳大利亚',
    'CA': '加拿大', 'SG': '新加坡', 'RU': '俄罗斯', 'HK': '中国香港',
    'MO': '中国澳门', 'TW': '中国台湾',
}


async def query_airport(icao):
    """查询机场信息。"""
    await load_airports()
    code = icao.upper()
    airport = (_airport_map or {}).get(code)
    if not airport:
        return f'未找到机场「{code}」'

    lines = [f'{code} {airport.get("name") or "未知"}国际机场']
    lines.append(f'类型：{_TYPE_MAP.get(airport.get("type")) or airport.get("type") or "未知"}')
    if airport.get('municipality'):
        lines.append(f'城市：{airport["municipality"]}')
    if airport.get('iso_country'):
        country = _COUNTRY_NAMES.get(airport['iso_country']) or airport['iso_country']
        lines.append(f'国家：{country}')
    if airport.get('latitude_deg') and airport.get('longitude_deg'):
        lat = float(airport['latitude_deg'])
        lon = float(airport['longitude_deg'])
        lines.append(f'坐标：{lat:.4f}, {lon:.4f}')
    if airport.get('elevation_ft'):
        lines.append(f'标高：{airport["elevation_ft"]} ft')
    if airport.get('home_link'):
        lines.append(f'网址：{airport["home_link"]}')

    return '\n'.join(lines)
