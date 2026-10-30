"""CWFLY 飞控机器人 - OneBot 反向 WebSocket 入口。

职责：
1. 启动 WebSocket Server（NapCat 反向连接，端口 6700）
2. 验证 NapCat Token
3. 接收 OneBot 事件并交给命令路由
4. 管制上下线通知（含 ATIS / ATC INFO，最多等 10 秒让 ATIS 到达）

运行：cd d:\\CWFLY\\bot && python -m py.main
"""
import asyncio
import json
import time

import websockets

from . import config, onebot
from .commands.index import dispatch
from .fsd9 import ensure_fsd9_started, get_fsd9_client

# 管制等级映射（FSD rating -> 等级字符串）
RATING_MAP = {
    1: 'OBS', 2: 'S1', 3: 'S2', 4: 'S3', 5: 'C1', 6: 'C2', 7: 'C3',
    8: 'I1', 9: 'I2', 10: 'I3', 11: 'SUP', 12: 'ADM',
}


def rating_label(rating):
    return RATING_MAP.get(rating) or f'R{rating}'


def format_frequency(freq):
    """频率整数(EuroScope格式如18500=118.500MHz) -> "118.500 MHz"。"""
    try:
        n = int(freq)
    except (TypeError, ValueError):
        n = 0
    if not n:
        return '未知'
    if n >= 100000:
        # 完整 kHz 表示（如 118500 = 118.500 MHz）
        return f'{n / 1000:.3f} MHz'
    # EuroScope 紧凑表示：1 + 前两位 + . + 后三位
    return f'1{str(n // 1000).zfill(2)}.{str(n % 1000).zfill(3)} MHz'


def format_utc(sec):
    if not sec:
        return ''
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(sec))) + ' UTC'


def format_time_short(sec):
    """秒时间戳 -> "UTC HH:MM / CST HH:MM"（CST = UTC+8）。"""
    utc = time.gmtime(int(sec))
    cst = time.gmtime(int(sec) + 8 * 3600)
    return f'UTC {time.strftime("%H:%M", utc)} / CST {time.strftime("%H:%M", cst)}'


def format_duration(start_sec):
    """服务时长（秒）-> "X 时 Y 分"。"""
    total_min = max(0, int((time.time() - int(start_sec)) // 60))
    return f'{total_min // 60} 时 {total_min % 60} 分'


def build_controller_card(controller, ctype):
    callsign = controller.get('callsign') or ''
    realname = controller.get('realname') or ''
    cid = controller.get('cid') or ''
    level = rating_label(controller.get('rating'))
    freq = format_frequency(controller.get('frequency'))
    start_sec = controller.get('starttime') or int(time.time())

    if ctype == 'offline':
        return '\n'.join([
            f'[{callsign} 离线通知]',
            f'管制员: {cid} {callsign} {realname}'.strip(),
            f'下线时间: {format_time_short(start_sec)}',
            f'提供服务时长: {format_duration(start_sec)}',
            f'请范围内机组守听 122.8',
            '祝飞行愉快~',
        ])

    # ATC INFO：管制员发布的 ATIS 航站情报（有则显示，无则不显示）
    atis = (controller.get('atis') or '').strip()
    atc_info = [l.strip() for l in atis.split('\n') if l.strip()] if atis else []

    local_time = time.strftime('%H:%M:%S', time.localtime(int(start_sec)))
    lines = [
        f'[{callsign} 上线通知]',
        f'管制员：CID {cid} {realname}',
        f'管制等级：{level}',
        f'联系频率：{freq}',
        f'上线时间：{format_utc(start_sec)} / {local_time} 本地',
    ]
    if atc_info:
        lines.append('')
        lines.append('ATC INFO')
        lines.extend(atc_info)
    lines.append('')
    lines.append('请范围内机组自主联系')
    lines.append('祝联飞顺利~')
    return '\n'.join(lines)


# ========== 管制上下线通知 ==========
# 是否已就绪（等待 OneBot 连接建立后再推送，避免启动时快照刷屏）
_bot_ready = False
_clients = set()  # 已连接的 WebSocket 客户端
# 等待 ATIS 的控制器（上线通知延迟，最多等 10 秒让 ATIS 到达）
_pending_online = {}  # callsign(upper) -> {'controller': ..., 'timer': ...}


def announce_controller_online(controller):
    group_id = config.notify_group_id()
    if not _bot_ready or not group_id or not controller.get('callsign'):
        return
    key = str(controller['callsign']).upper()

    # 已带 ATIS：直接推送
    if controller.get('atis'):
        asyncio.create_task(push_online(controller))
        return

    # 等待 ATIS：若已有待发，先取消旧定时器
    if key in _pending_online:
        try:
            _pending_online[key]['timer'].cancel()
        except Exception:
            pass
    timer = asyncio.get_event_loop().call_later(10.0, _pending_online_timeout, key, controller)
    _pending_online[key] = {'controller': controller, 'timer': timer}


def _pending_online_timeout(key, controller):
    _pending_online.pop(key, None)
    asyncio.create_task(push_online(controller))


async def push_online(controller):
    group_id = config.notify_group_id()
    if not group_id or not controller.get('callsign'):
        return
    text = build_controller_card(controller, 'online')
    await _broadcast(text)
    print(f'[Bot] 上线通知已推送 {controller["callsign"]} → group={group_id}')


async def on_controller_atis(payload):
    """收到 ATIS 时，若该管制员正在等待上线通知，立即推送。"""
    callsign = payload.get('callsign') or ''
    key = str(callsign).upper()
    pending = _pending_online.get(key)
    if not pending:
        return
    try:
        pending['timer'].cancel()
    except Exception:
        pass
    _pending_online.pop(key, None)
    await push_online(pending['controller'])


def announce_controller_offline(controller):
    group_id = config.notify_group_id()
    if not _bot_ready or not group_id or not controller.get('callsign'):
        return
    key = str(controller['callsign']).upper()
    # 取消该管制员待发的上线通知
    if key in _pending_online:
        try:
            _pending_online[key]['timer'].cancel()
        except Exception:
            pass
        _pending_online.pop(key, None)
    asyncio.create_task(_push_offline(controller))


async def _push_offline(controller):
    group_id = config.notify_group_id()
    if not group_id:
        return
    text = build_controller_card(controller, 'offline')
    await _broadcast(text)
    print(f'[Bot] 下线通知已推送 {controller["callsign"]} → group={group_id}')


async def _broadcast(text):
    group_id = config.notify_group_id()
    for ws in list(_clients):
        try:
            await onebot.send_group_message(ws, group_id, text)
        except Exception:
            pass


def _set_ready():
    global _bot_ready
    _bot_ready = True
    print('[Bot] Ready, 管制上下线通知已启用')


def _extract_token(ws):
    """从请求头（Authorization: Bearer）或查询串（access_token）提取 Token。

    websockets 16 的 ServerConnection 通过 .request.headers 暴露请求头
    （无 request_headers 属性），键名大小写不敏感匹配。
    """
    try:
        request = ws.request
        auth = ''
        for k, v in request.headers.items():
            if k.lower() == 'authorization':
                auth = v
                break
        if auth.lower().startswith('bearer '):
            return auth[7:]
    except Exception:
        pass
    try:
        qs = ws.request.path or ''
        if '?' in qs:
            qs = qs.split('?', 1)[1]
        for kv in qs.split('&'):
            if '=' in kv:
                k, _, v = kv.partition('=')
                if k == 'access_token':
                    return v
    except Exception:
        pass
    return ''


async def _connection(ws):
    # Token 验证
    token = _extract_token(ws)
    # 安全(2026-10-25 审计 P1-2): fail-closed, 未配置 token 直接拒绝
    if not config.ACCESS_TOKEN or token != config.ACCESS_TOKEN:
        print(f'[OneBot] Token rejected from {ws.remote_address}')
        await ws.close(1008, 'Unauthorized')
        return

    print(f'[OneBot] Connection from {ws.remote_address}')
    _clients.add(ws)

    # 首个连接稳定后启用管制上下线推送
    if not _bot_ready:
        asyncio.get_event_loop().call_later(2.0, _set_ready)

    try:
        async for raw in ws:
            try:
                event = json.loads(raw)
                await dispatch(ws, event)
            except Exception as e:
                print(f'[OneBot] Parse error: {e}')
    finally:
        _clients.discard(ws)
        print('[OneBot] Connection closed')


async def _wire_fsd():
    client = get_fsd9_client()
    client.on('controller:add', lambda c: announce_controller_online(c))
    client.on('controller:remove', lambda c: announce_controller_offline(c))
    client.on('controller:atis', lambda p: asyncio.create_task(on_controller_atis(p)))


async def main():
    await ensure_fsd9_started()
    await _wire_fsd()
    async with websockets.serve(_connection, config.WS_HOST, config.WS_PORT):
        print(f'[OneBot] WS server listening on {config.WS_HOST}:{config.WS_PORT}')
        await asyncio.Event().wait()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n[Bot] 已停止')
