"""航路查询命令。"""
from .. import onebot, validator
from ..services.route import query_route


async def handle_route(ws, event, args):
    if not args or len(args) < 2:
        await onebot.reply(ws, event, '使用方法：/航路 ZSPD ZBAA')
        return

    dep = validator.normalize_icao(args[0])
    arr = validator.normalize_icao(args[1])
    if not dep or not arr:
        await onebot.reply(ws, event, 'ICAO 代码必须为 4 位字母数字。')
        return

    text = await query_route(dep, arr)
    await onebot.reply(ws, event, text)
