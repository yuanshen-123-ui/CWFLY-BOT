"""AI 聊天命令。"""
from .. import onebot
from ..services.ai import normal_ai


async def handle_normal_ai(ws, event, args):
    if not args:
        await onebot.reply(ws, event, '使用方法：/chat 什么是 PBN？')
        return

    message = ' '.join(args)[:1000]
    text = await normal_ai(message)
    await onebot.reply(ws, event, text)
