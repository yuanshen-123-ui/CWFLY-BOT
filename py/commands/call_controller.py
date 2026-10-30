"""呼叫管制命令（/呼叫管制、/呼叫2325）。"""
import time

from .. import config, onebot
from ..rate_limit import check_global_cooldown, check_user_cooldown
from ..services.fsd import get_fsd_status


async def handle_call_controller(ws, event, args):
    """/呼叫管制 - 发送管制呼叫到管制群（同 QQ 5 分钟冷却，全群 1 分钟冷却）。"""
    # 仅群聊可用
    if event.get('message_type') != 'group':
        await onebot.send_group_message(ws, event.get('user_id'), '/呼叫管制 仅支持群聊。')
        return

    user_id = str(event.get('user_id'))
    group_id = str(event.get('group_id'))
    control_group_id = config.control_group_id()

    if not control_group_id:
        await onebot.send_group_message(ws, group_id, '管制群未配置（CONTROL_GROUP_ID）。')
        return

    # 用户冷却 5 分钟
    user_wait = check_user_cooldown(f'call:{user_id}', 300)
    if user_wait:
        await onebot.send_group_message(ws, group_id, f'您 {user_wait} 秒后才能再次呼叫管制。')
        return

    # 全群冷却 1 分钟
    global_wait = check_global_cooldown(f'call:group:{group_id}', 60)
    if global_wait:
        await onebot.send_group_message(ws, group_id, f'本群 {global_wait} 秒前刚呼叫过管制。')
        return

    # 获取当前 FSD 在线状态
    online_info = ''
    try:
        data = await get_fsd_status()
        controllers = data.get('controllers') or []
        if controllers:
            ctrl_list = '、'.join(c.get('callsign') for c in controllers)
            online_info = f'\n当前在线管制：{ctrl_list}\n（已在 FSD 在线，无需呼叫）'
    except Exception:
        online_info = '\nFSD 状态服务暂时不可用。'

    sender = event.get('sender') or {}
    nickname = sender.get('nickname') or sender.get('card') or f'用户{user_id}'
    time_str = time.strftime('%H:%M:%S')
    message = '\n'.join([
        '管制呼叫',
        f'请求人：{nickname}（{user_id}）',
        f'来源群：{event.get("group_id")}',
        f'时间：{time_str}',
        '请在线管制员查看 FSD 状态并响应。',
        online_info,
    ])

    # 发送到管制群
    await onebot.send_group_message(ws, control_group_id, message)
    # 回复请求群
    await onebot.send_group_message(ws, group_id, '呼叫已发送到管制群，请等待管制员响应。')


async def handle_call_2325(ws, event, args):
    """/呼叫2325 - 呼叫指定管制员 2325（私聊到其 QQ）。"""
    # 仅群聊可用
    if event.get('message_type') != 'group':
        await onebot.send_private_message(ws, event.get('user_id'), '/呼叫2325 仅支持群聊。')
        return

    user_id = str(event.get('user_id'))
    group_id = str(event.get('group_id'))
    target_qq = config.call_2325_qq()

    # 用户冷却 5 分钟
    user_wait = check_user_cooldown(f'call2325:{user_id}', 300)
    if user_wait:
        await onebot.send_group_message(ws, group_id, f'您 {user_wait} 秒后才能再次呼叫管制员 2325。')
        return

    # 全群冷却 1 分钟
    global_wait = check_global_cooldown(f'call2325:group:{group_id}', 60)
    if global_wait:
        await onebot.send_group_message(ws, group_id, f'本群 {global_wait} 秒前刚呼叫过管制员 2325。')
        return

    sender = event.get('sender') or {}
    nickname = sender.get('nickname') or sender.get('card') or f'用户{user_id}'
    time_str = time.strftime('%H:%M:%S')
    extra = f'\n请求内容：{" ".join(args)}' if args else ''
    message = '\n'.join([
        '管制呼叫（2325）',
        f'请求人：{nickname}（{user_id}）',
        f'来源群：{event.get("group_id")}',
        f'时间：{time_str}',
        f'请管制员 2325 响应。{extra}',
    ])

    # 私聊发送给 2325
    await onebot.send_private_message(ws, target_qq, message)
    # 回复请求群
    await onebot.send_group_message(ws, group_id, '呼叫已发送给管制员 2325，请等待响应。')
