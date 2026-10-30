"""机组查询命令。"""
from .. import onebot, validator
from ..services.fsd import format_pilot_list, format_pilot_query


async def handle_pilot_query(ws, event, args):
    # 有呼号时精确查询，无呼号时返回列表
    if not args:
        text = await format_pilot_list()
        await onebot.reply(ws, event, text)
        return

    callsign = args[0].strip().upper()
    if not validator.is_valid_callsign(callsign):
        await onebot.reply(ws, event, '呼号格式无效（2-12 位字母数字）。')
        return

    text = await format_pilot_query(callsign)
    await onebot.reply(ws, event, text)
