"""机场查询命令。"""
from .. import onebot, validator
from ..services.airport import query_airport


async def handle_airport(ws, event, args):
    if not args:
        await onebot.reply(ws, event, '使用方法：/机场查询 ZSPD')
        return

    icao = validator.normalize_icao(args[0])
    if not icao:
        await onebot.reply(ws, event, 'ICAO 代码必须为 4 位字母数字。')
        return

    text = await query_airport(icao)
    await onebot.reply(ws, event, text)
