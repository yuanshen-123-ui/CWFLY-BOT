"""OneBot 11 协议工具函数（向已连接的 WebSocket 客户端发送 API 请求）。"""
import json
import uuid


def _echo():
    return str(uuid.uuid4())


async def send_group_message(ws, group_id, message):
    """发送群消息。ws 为 websockets 连接对象。"""
    payload = json.dumps({
        'action': 'send_group_msg',
        'params': {'group_id': int(group_id), 'message': message},
        'echo': _echo(),
    })
    await _send(ws, payload)


async def send_private_message(ws, user_id, message):
    """发送私聊消息。"""
    payload = json.dumps({
        'action': 'send_private_msg',
        'params': {'user_id': int(user_id), 'message': message},
        'echo': _echo(),
    })
    await _send(ws, payload)


async def reply(ws, event, message):
    """按事件类型回复（群聊→群消息，私聊→私聊消息）。"""
    if event.get('message_type') == 'group':
        await send_group_message(ws, event.get('group_id'), message)
    else:
        await send_private_message(ws, event.get('user_id'), message)


async def upload_group_file(ws, group_id, file_path, file_name):
    """上传群文件。file_path 为绝对路径。"""
    payload = json.dumps({
        'action': 'upload_group_file',
        'params': {
            'group_id': int(group_id),
            'file': file_path.replace('\\', '/'),
            'name': file_name,
        },
        'echo': _echo(),
    })
    await _send(ws, payload)


async def set_group_add_request(ws, flag, sub_type, approve, reason=''):
    """处理群加入请求（通过 / 拒绝）。

    flag 来自 request 事件的 flag 字段；sub_type 为 'add'（主动加群）或 'invite'（被邀请）。
    """
    payload = json.dumps({
        'action': 'set_group_add_request',
        'params': {
            'flag': flag,
            'sub_type': sub_type,
            'approve': approve,
            'reason': reason,
        },
        'echo': _echo(),
    })
    await _send(ws, payload)


async def _send(ws, payload):
    try:
        await ws.send(payload)
    except Exception as e:
        print(f'[OneBot] send error: {e}')
