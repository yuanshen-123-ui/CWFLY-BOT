"""在线状态命令。"""
from .. import onebot
from ..services.fsd import format_online_status


async def handle_online_status(ws, event, args):
    text = await format_online_status()
    await onebot.reply(ws, event, text)
