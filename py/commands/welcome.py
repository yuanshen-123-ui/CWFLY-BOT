"""入群欢迎。"""
from .. import config, onebot, validator

WELCOME_TEXT = """欢迎来到CW模拟飞行连飞平台
我们是一个现代化，优质的模拟飞行连飞平台
祝各位飞行愉快，管制愉快
友情链接：
官网：https://www.cwflysim.cn
论坛：https://cwforum.org
空管中心：https://atc.cwflysim.cn
Swift / EuroScope：fsd.cwflysim.cn
文档站：https://docs.cwflysim.cn
ts : ts.cwflysim.cn"""


async def handle_group_increase(ws, event):
    """处理群成员增加（入群）通知。"""
    group_id = event.get('group_id')
    user_id = event.get('user_id')
    if not group_id or not user_id:
        return

    # 机器人自己入群（被拉进群）不触发欢迎
    if str(user_id) == str(config.BOT_SELF_ID):
        return

    # 仅限允许的群
    if not validator.is_allowed_group(group_id):
        return

    message = [
        {'type': 'at', 'data': {'qq': str(user_id)}},
        {'type': 'text', 'data': {'text': '\n' + WELCOME_TEXT}},
    ]
    await onebot.send_group_message(ws, group_id, message)
    print(f'[Welcome] 新成员 {user_id} 加入群 {group_id}，已发送欢迎')
