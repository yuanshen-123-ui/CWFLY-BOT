"""METAR / TAF 查询命令。"""
import re

from .. import onebot, validator
from ..services.weather import format_metar, format_taf


async def handle_metar(ws, event, args):
    if not args:
        await onebot.reply(ws, event, '使用方法：/metar ZSPD')
        return

    icao = validator.normalize_icao(args[0])
    if not icao:
        await onebot.reply(ws, event, f'无效的 ICAO 代码：「{args[0]}」应为 4 位字母（如 ZSPD）。')
        return

    text = await format_metar(icao)
    await onebot.reply(ws, event, text)


async def handle_taf(ws, event, args):
    if not args:
        await onebot.reply(ws, event, '使用方法：/taf ZBAA,ZSPD')
        return

    # 逐个校验，非法输入明确提示（如 2 位国家码 AD、含数字的代码）
    raw_items = [x for x in re.split(r'[,，\s]+', ','.join(args)) if x]
    if not raw_items:
        await onebot.reply(ws, event, '使用方法：/taf ZBAA,ZSPD')
        return
    invalid = [i for i in raw_items if not validator.normalize_icao(i)]
    if invalid:
        await onebot.reply(ws, event, f'无效的 ICAO 代码：{"、".join(invalid)}（应为 4 位字母，如 ZSPD）')
        return

    text = await format_taf(','.join(raw_items[:5]))
    await onebot.reply(ws, event, text)
