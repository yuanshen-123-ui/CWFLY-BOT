"""近期连飞活动查询命令。"""
from .. import config, onebot
from ..services import http


async def handle_event(ws, event, args):
    try:
        resp = await http.http_get(f'{config.API_BASE}/events', timeout=8)
        if resp.status_code != 200:
            await onebot.reply(ws, event, '查询失败，服务器异常')
            return

        data = resp.json()
        events = data.get('data') or []
        if not events:
            await onebot.reply(ws, event, '暂无近期活动')
            return

        # 最多显示 5 个
        lines = []
        for i, e in enumerate(events[:5]):
            dep = e.get('dep') or e.get('depIcao') or '??'
            arr = e.get('arr') or e.get('arrIcao') or '??'
            lines.append(
                f"{i + 1}. {e.get('title') or '未命名活动'}\n"
                f"   日期：{e.get('date') or '-'}  {dep} → {arr}\n"
                f"   状态：{e.get('status') or '-'}")

        await onebot.reply(ws, event, f'近期活动（共{len(events)}个）：\n\n' + '\n\n'.join(lines))
    except Exception:
        await onebot.reply(ws, event, '查询失败：网络错误')
