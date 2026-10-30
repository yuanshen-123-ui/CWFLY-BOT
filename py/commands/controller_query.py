"""管制查询命令。"""
from .. import onebot, validator
from ..services.fsd import format_controller_list, format_controller_query


async def handle_controller_query(ws, event, args):
    if not args:
        text = await format_controller_list()
        await onebot.reply(ws, event, text)
        return

    callsign = args[0].strip().upper()
    if not validator.is_valid_callsign(callsign):
        await onebot.reply(ws, event, '呼号格式无效。')
        return

    text = await format_controller_query(callsign)
    await onebot.reply(ws, event, text)
