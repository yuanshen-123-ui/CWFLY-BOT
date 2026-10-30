"""航空气象服务 - 复用现有 CWFLY 后端 API。"""
import re

from .. import config, validator
from . import http

CWFLY_API_URL = config.CWFLY_API_URL


async def get_weather(icao):
    """获取单个机场的气象数据。返回 {metar, taf} 或 None。"""
    url = f'{CWFLY_API_URL}/weather?icao={icao}'
    try:
        resp = await http.http_get(url, timeout=8)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get('success'):
            return None
        return data.get('data') or None
    except Exception:
        return None


async def format_metar(icao):
    try:
        data = await get_weather(icao)
        if not data:
            return f'无法获取 {icao} 的气象数据。'
        metar = data.get('metar') or '无 METAR 数据'
        return f'{icao} METAR\n{metar}'
    except Exception:
        return f'{icao} 气象服务暂时不可用。'


async def format_taf(icao_input):
    """格式化单个或多个机场的 TAF（最多 5 个）。服务层兜底只查询合法 ICAO。"""
    icaos = [x for x in (validator.normalize_icao(i) for i in re.split(r'[,，\s]+', icao_input)) if x][:5]
    if not icaos:
        return '请指定有效的 ICAO 代码（4 位字母）。'
    results = []
    for icao in icaos:
        try:
            data = await get_weather(icao)
            if not data:
                results.append(f'{icao}：无法获取数据')
            else:
                taf = data.get('taf') or '无 TAF 数据'
                results.append(f'{icao} TAF\n{taf}')
        except Exception:
            results.append(f'{icao}：无法获取数据')
    return '\n\n'.join(results)
