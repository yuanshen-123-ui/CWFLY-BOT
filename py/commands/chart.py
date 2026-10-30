"""航图查询命令（与 Node 版一致，暂未注册到命令路由）。"""
from .. import config, onebot
from ..services import http


async def handle_chart(ws, event, args):
    icao = (args[0] if args else '').upper()
    if not icao:
        await onebot.reply(ws, event, '用法：/chart <ICAO>\n例如：/chart ZBAA')
        return

    try:
        resp = await http.http_get(
            f'{config.API_BASE}/charts?icao={icao}&provider=jeppesen', timeout=12)
        if resp.status_code != 200:
            await onebot.reply(ws, event, '航图查询失败')
            return

        data = resp.json()
        d = data.get('data') or {}
        charts = (d.get('charts') if isinstance(d, dict) else None) \
            or (d.get('data') if isinstance(d, dict) else None) \
            or (d if isinstance(d, list) else [])

        if not charts:
            await onebot.reply(ws, event, f'未找到 {icao} 的航图')
            return

        # 按类型分组
        groups = {}
        for c in charts:
            name = (c.get('name') or c.get('id') or '').lower()
            if 'sid' in name or '离场' in name:
                t = '离场 SID'
            elif 'star' in name or '进场' in name:
                t = '进场 STAR'
            elif 'iap' in name or '进近' in name or 'ils' in name or 'vor' in name:
                t = '进近 IAP'
            elif 'taxi' in name or '停机' in name or 'park' in name:
                t = '停机位'
            elif '机场' in name or 'general' in name or 'ref' in name:
                t = '参考'
            else:
                t = '其他'
            groups.setdefault(t, []).append(c.get('name') or c.get('id') or '')

        lines = [f'{icao} 航图（共{len(charts)}张）：']
        for t, items in groups.items():
            lines.append(f'\n【{t}】{len(items)}张')
            for n in items[:3]:
                lines.append(f'  · {n}')

        await onebot.reply(ws, event, '\n'.join(lines))
    except Exception:
        await onebot.reply(ws, event, '航图查询失败')
