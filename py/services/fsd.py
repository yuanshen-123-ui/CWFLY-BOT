"""FSD 在线状态查询服务。

优先通过 FSD9 协议直连获取实时数据，
当 FSD9 不可用时，自动回退到 HTTP API。
"""
import asyncio
import time

from .. import config
from ..fsd9 import get_fsd9_client
from . import http

FSD_API_URL = config.FSD_API_URL


def is_system_callsign(callsign):
    """系统连接（CW-BOT/CW-MAP-*/CW-FP*）不计入在线统计。"""
    return (callsign or '').upper().startswith('CW-')


def get_fsd9_status():
    client = get_fsd9_client()
    if not client.is_ready:
        return None
    pilots = [p for p in client.pilot_list if not is_system_callsign(p.get('callsign'))]
    controllers = [c for c in client.controller_list if not is_system_callsign(c.get('callsign'))]
    return {'pilots': pilots, 'controllers': controllers, 'clients': pilots + controllers}


async def get_api_status():
    """HTTP API 后备。"""
    resp = await http.http_get(FSD_API_URL, timeout=5)
    if resp.status_code != 200:
        raise RuntimeError(f'FSD HTTP {resp.status_code}')
    data = resp.json()
    pilots = data.get('pilots') or [
        c for c in data.get('clients') or [] if c.get('type') == 'PILOT']
    controllers = data.get('controllers') or [
        c for c in data.get('clients') or [] if c.get('type') == 'ATC']
    pilots = [p for p in pilots if not is_system_callsign(p.get('callsign'))]
    controllers = [c for c in controllers if not is_system_callsign(c.get('callsign'))]
    return {'pilots': pilots, 'controllers': controllers, 'total': len(pilots) + len(controllers)}


async def get_fsd_status():
    """统一查询接口（FSD9 → API 后备）。"""
    # 等待 FSD9 连接就绪（最多 ~4 秒），避免首次查询误走不可用的 HTTP 回退
    client = get_fsd9_client()
    if not client.is_ready:
        for _ in range(8):
            await asyncio.sleep(0.5)
            if client.is_ready:
                break
    fsd9 = get_fsd9_status()
    if fsd9:
        return {
            'pilots': fsd9['pilots'],
            'controllers': fsd9['controllers'],
            'total': len(fsd9['clients']),
            'source': 'fsd9',
        }
    api = await get_api_status()
    return {
        'pilots': api['pilots'],
        'controllers': api['controllers'],
        'total': api['total'],
        'source': 'api',
    }


async def query_pilot(callsign):
    key = callsign.upper()
    client = get_fsd9_client()
    if client.is_ready:
        pilot = client.get_pilot(key)
        if pilot:
            return pilot
        client.query_client(key)
        return None
    try:
        data = await get_fsd_status()
        return next((p for p in data['pilots']
                     if (p.get('callsign') or '').upper() == key), None)
    except Exception:
        return None


async def query_controller(callsign):
    key = callsign.upper()
    client = get_fsd9_client()
    if client.is_ready:
        ctrl = client.get_controller(key)
        if ctrl:
            return ctrl
        client.query_client(key)
        return None
    try:
        data = await get_fsd_status()
        return next((c for c in data['controllers']
                     if (c.get('callsign') or '').upper() == key), None)
    except Exception:
        return None


# ========== 格式化输出 ==========
FACILITY_NAMES = ['———', 'OBS', 'FSS', 'DEL', 'GND', 'TWR', 'APP', 'CTR']
RATING_NAMES = ['SUS', 'OBS', 'S1', 'S2', 'S3', 'C1', 'C2', 'C3',
                'I1', 'I2', 'I3', 'SUP', 'ADM']


def _freq_label(freq):
    try:
        return f'{int(freq) / 1000:.3f}'
    except (TypeError, ValueError):
        return ''


async def format_online_status():
    try:
        data = await get_fsd_status()
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        source = 'FSD9直连' if data['source'] == 'fsd9' else 'HTTP API'
        return '\n'.join([
            f'在线机组：{len(data["pilots"])}',
            f'在线管制：{len(data["controllers"])}',
            f'总连接数：{data["total"]}',
            f'查询时间：{now}',
        ])
    except Exception:
        return 'FSD 服务暂时不可用，请稍后重试。'


async def format_pilot_query(callsign):
    pilot = await query_pilot(callsign)
    if not pilot:
        return f'未找到在线机组「{callsign}」'
    plan = pilot.get('plan') or {}
    lines = [f'在线机组 {pilot.get("callsign")}']
    if pilot.get('cid'):
        lines.append(f'CID：{pilot["cid"]}')
    if pilot.get('realname'):
        lines.append(f'姓名：{pilot["realname"]}')

    # ---- 飞行计划 ----
    if plan.get('type'):
        rules = str(plan['type']).upper()
        lines.append(f'计划类型：{"IFR 仪表" if rules == "I" else "VFR 目视" if rules == "V" else rules}')
    ac = pilot.get('aircraft') or plan.get('aircraft') or ''
    if ac:
        lines.append(f'机型：{ac}')
    dep = plan.get('depairport') or pilot.get('dep') or ''
    dest = plan.get('destairport') or pilot.get('dest') or ''
    if dep and dest:
        lines.append(f'航线：{dep} → {dest}')
    if plan.get('altitude'):
        lines.append(f'计划高度：{plan["altitude"]}')
    if plan.get('tascruise'):
        lines.append(f'巡航速度：{plan["tascruise"]}')
    if plan.get('hrsenroute') or plan.get('minenroute'):
        hrs = plan.get('hrsenroute') or 0
        mins = plan.get('minenroute') or 0
        lines.append(f'预计时间：{hrs}h{mins}m')
    if plan.get('altairport'):
        lines.append(f'备降场：{plan["altairport"]}')
    route = plan.get('route') or pilot.get('route') or ''
    if route:
        lines.append(f'航路：{route[:120] + "…" if len(route) > 120 else route}')
    if plan.get('remarks'):
        lines.append(f'备注：{plan["remarks"]}')

    # ---- 实时状态 ----
    if pilot.get('altitude'):
        alt = pilot['altitude']
        if isinstance(alt, str):
            label = alt
        else:
            try:
                label = f'FL{round(int(alt) / 100)}'
            except (TypeError, ValueError):
                label = str(alt)
        lines.append(f'当前高度：{label}')
    if pilot.get('groundspeed'):
        lines.append(f'地速：{pilot["groundspeed"]} kt')
    if pilot.get('transponder'):
        lines.append(f'应答机：{pilot["transponder"]}')

    return '\n'.join(lines)


async def format_controller_query(callsign):
    ctrl = await query_controller(callsign)
    if not ctrl:
        return f'未找到在线管制「{callsign}」'
    lines = [f'在线管制 {ctrl.get("callsign")}']
    if ctrl.get('realname'):
        lines.append(f'姓名：{ctrl["realname"]}')
    try:
        ft = int(ctrl.get('facilitytype', -1))
    except (TypeError, ValueError):
        ft = -1
    lines.append(f'席位：{FACILITY_NAMES[ft] if 0 <= ft < len(FACILITY_NAMES) else ft}')
    if ctrl.get('frequency'):
        lines.append(f'频率：{_freq_label(ctrl["frequency"])}')
    try:
        r = int(ctrl.get('rating', -1))
    except (TypeError, ValueError):
        r = -1
    if r >= 0:
        lines.append(f'等级：{RATING_NAMES[r] if 0 <= r < len(RATING_NAMES) else r}')
    if ctrl.get('starttime'):
        t = time.strftime('%H:%M:%S', time.localtime(int(ctrl['starttime'])))
        lines.append(f'上线时间：{t}')
    return '\n'.join(lines)


async def format_pilot_list():
    try:
        data = await get_fsd_status()
        pilots = data['pilots']
        if not pilots:
            return '当前无在线机组。'
        items = []
        for p in pilots[:20]:
            plan = p.get('plan') or {}
            dep = plan.get('depairport') or ''
            dest = plan.get('destairport') or ''
            items.append(f'{p.get("callsign")} {dep}→{dest}' if dep and dest else p.get('callsign'))
        more = f'\n...及另外 {len(pilots) - 20} 人' if len(pilots) > 20 else ''
        return f'在线机组（{len(pilots)}）\n' + '\n'.join(items) + more
    except Exception:
        return 'FSD 服务暂时不可用。'


async def format_controller_list():
    try:
        data = await get_fsd_status()
        controllers = data['controllers']
        if not controllers:
            return '当前无在线管制。'
        items = []
        for c in controllers:
            freq = f' {_freq_label(c.get("frequency"))}' if c.get('frequency') else ''
            items.append(f'{c.get("callsign")}{freq}')
        return f'在线管制（{len(controllers)}）\n' + '\n'.join(items)
    except Exception:
        return 'FSD 服务暂时不可用。'
