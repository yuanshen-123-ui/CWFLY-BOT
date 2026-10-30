"""冒烟测试：FSD 报文解析 + 命令分发（临时文件，验证后可删除）。"""
import asyncio

from py.fsd9 import parse_client_add_line
from py.commands.index import dispatch

# 1. 解析 fsd.log 中的真实报文
cases = [
    ('#AAZGGG_TWR::Test TWR:5966:cwfly2024:7:9', True),
    ('#AAZBAA_TWR:SERVER:5966:5966:Aa1002144621#$%:10:9:1:0:40.07333:116.59833:100', True),
    ('#APCSA123:1:1:1111:pwd:2:9:0:测试机长', False),
]
for line, atc in cases:
    r = parse_client_add_line(line, atc)
    print(f'PARSED {line[:30]!r} -> {r}')


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send(self, payload):
        self.sent.append(payload)


async def main():
    ws = FakeWS()

    # /帮助（群消息）
    await dispatch(ws, {
        'post_type': 'message', 'message_type': 'group',
        'group_id': 868785291, 'user_id': 12345,
        'message': [{'type': 'text', 'data': {'text': '/帮助'}}],
    })
    print('--- /帮助 发送条数:', len(ws.sent))
    if ws.sent:
        import json
        body = json.loads(ws.sent[-1])
        print('action:', body['action'], '| message 前40字:', str(body['params']['message'])[:40])

    # 非白名单群应被忽略
    ws.sent.clear()
    await dispatch(ws, {
        'post_type': 'message', 'message_type': 'group',
        'group_id': 999999, 'user_id': 12345,
        'message': [{'type': 'text', 'data': {'text': '/帮助'}}],
    })
    print('--- 非白名单群 发送条数:', len(ws.sent), '(应为 0)')

    # @机器人
    ws.sent.clear()
    await dispatch(ws, {
        'post_type': 'message', 'message_type': 'group',
        'group_id': 868785291, 'user_id': 12345,
        'message': [
            {'type': 'at', 'data': {'qq': '3822780061'}},
            {'type': 'text', 'data': {'text': '你好'}},
        ],
    })
    print('--- @机器人 发送条数:', len(ws.sent), '(应含 思考中…)')

    # 入群欢迎（notice）
    ws.sent.clear()
    await dispatch(ws, {
        'post_type': 'notice', 'notice_type': 'group_increase',
        'group_id': 868785291, 'user_id': 55555,
    })
    print('--- 入群欢迎 发送条数:', len(ws.sent), '(应为 1)')


asyncio.run(main())
print('SMOKE TEST DONE')
