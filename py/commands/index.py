"""命令路由：严格前缀匹配，长命令在前避免误匹配。"""
from .. import config, onebot, validator
from ..rate_limit import check_user_cooldown
from . import ai, airport, call_controller, controller_query, event, group_request, help
from . import metar, online_status, pilot_query, route, welcome

# 命令定义：主命令 + 中英文别名（与 Node 版一致）
ROUTES = [
    {'cmd': '/在线状态', 'aliases': ['/online'], 'handler': online_status.handle_online_status, 'cooldown': 3},
    {'cmd': '/机组查询', 'aliases': ['/pilot', '/pilotquery'], 'handler': pilot_query.handle_pilot_query, 'cooldown': 2},
    {'cmd': '/管制查询', 'aliases': ['/controller', '/atc'], 'handler': controller_query.handle_controller_query, 'cooldown': 2},
    {'cmd': '/机场查询', 'aliases': ['/airport'], 'handler': airport.handle_airport, 'cooldown': 2},
    {'cmd': '/呼叫管制', 'aliases': ['/call', '/callcontroller'], 'handler': call_controller.handle_call_controller, 'cooldown': 3},
    {'cmd': '/呼叫2325', 'aliases': ['/call2325'], 'handler': call_controller.handle_call_2325, 'cooldown': 3},
    {'cmd': '/metar', 'aliases': ['/气象', '/气象报文'], 'handler': metar.handle_metar, 'cooldown': 2},
    {'cmd': '/taf', 'aliases': ['/预报'], 'handler': metar.handle_taf, 'cooldown': 2},
    {'cmd': '/航路', 'aliases': ['/route'], 'handler': route.handle_route, 'cooldown': 3},
    {'cmd': '/event', 'aliases': ['/活动'], 'handler': event.handle_event, 'cooldown': 3},
    {'cmd': '/chat', 'aliases': ['/聊天'], 'handler': ai.handle_normal_ai, 'cooldown': 5},
    {'cmd': '/帮助', 'aliases': ['/help'], 'handler': help.handle_help, 'cooldown': 1},
]


async def dispatch(ws, event):
    """分发消息事件到命令处理函数。"""
    # 处理请求事件（群入群申请自动审核）
    if event.get('post_type') == 'request':
        if event.get('request_type') == 'group':
            try:
                await group_request.handle_group_request(ws, event)
            except Exception as e:
                print(f'[GroupRequest] error: {e}')
        return

    # 处理通知事件（入群欢迎等）
    if event.get('post_type') == 'notice':
        if event.get('notice_type') == 'group_increase':
            try:
                await welcome.handle_group_increase(ws, event)
            except Exception as e:
                print(f'[Welcome] error: {e}')
        return

    # 仅处理消息事件
    if event.get('post_type') != 'message':
        return

    # 群消息检查白名单
    if event.get('message_type') == 'group' and not validator.is_allowed_group(event.get('group_id')):
        return

    user_id = str(event.get('user_id'))

    # --- @机器人 检测 ---
    message = event.get('message')
    if isinstance(message, list):
        at_index = None
        for i, seg in enumerate(message):
            if (seg.get('type') == 'at'
                    and str(seg.get('data', {}).get('qq', '')) == config.BOT_SELF_ID):
                at_index = i
                break
        if at_index is not None:
            # 提取 @ 之后的所有文本
            after_at = ''.join(
                seg.get('data', {}).get('text', '')
                for seg in message[at_index + 1:]
                if seg.get('type') == 'text'
            ).strip()
            if after_at:
                wait = check_user_cooldown(f'cmd:@bot:{user_id}', 5)
                if not wait:
                    try:
                        await ai.handle_normal_ai(ws, event, [after_at])
                    except Exception as e:
                        print(f'[Command] @bot error: {e}')
                        await _send_error(ws, event)
                return

    # 提取纯文本
    text = extract_plain_text(event)
    if not text:
        return

    # 严格以空白拆分，第一个字段作为命令
    parts = text.strip().split()
    command = parts[0]
    args = parts[1:]

    # 匹配命令（主命令或中英文别名）
    for r in ROUTES:
        if command == r['cmd'] or command in r['aliases']:
            # 检查冷却
            wait = check_user_cooldown(f"cmd:{r['cmd']}:{user_id}", r['cooldown'])
            if wait:
                return  # 冷却中，静默忽略
            try:
                await r['handler'](ws, event, args)
            except Exception as e:
                print(f"[Command] {r['cmd']} error: {e}")
                await _send_error(ws, event)
            return


async def _send_error(ws, event):
    try:
        await onebot.reply(ws, event, '命令执行出错，请稍后重试。')
    except Exception:
        pass


def extract_plain_text(event):
    """从 OneBot 事件中提取纯文本内容。"""
    msg = event.get('message')
    if isinstance(msg, str):
        return msg
    if isinstance(msg, list):
        text = ''.join(seg.get('data', {}).get('text', '')
                       for seg in msg if seg.get('type') == 'text').strip()
        return text or None
    return None
