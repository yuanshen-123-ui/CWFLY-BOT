/**
 * 入群欢迎
 * 当新成员加入群时发送欢迎消息（OneBot notice / group_increase）
 */

import { sendGroupMessage } from '../utils/onebot.js'
import { isAllowedGroup } from '../utils/validator.js'

const WELCOME_TEXT = `欢迎来到CW模拟飞行连飞平台
我们是一个现代化，优质的模拟飞行连飞平台
祝各位飞行愉快，管制愉快
友情链接：
官网：https://www.cwflysim.cn
论坛：https://cwforum.org
空管中心：https://atc.cwflysim.cn
Swift / EuroScope：fsd.cwflysim.cn
文档站：https://docs.cwflysim.cn
ts : ts.cwflysim.cn`

/**
 * 处理群成员增加（入群）通知
 * @param {import('ws').WebSocket} ws
 * @param {object} event - OneBot 通知事件（post_type=notice, notice_type=group_increase）
 */
export function handleGroupIncrease(ws, event) {
  const { group_id, user_id } = event
  if (!group_id || !user_id) return

  // 机器人自己入群（被拉进群）不触发欢迎
  if (String(user_id) === String(process.env.BOT_SELF_ID)) return

  // 仅限允许的群
  if (!isAllowedGroup(group_id)) return

  const message = [
    { type: 'at', data: { qq: String(user_id) } },
    { type: 'text', data: { text: '\n' + WELCOME_TEXT } }
  ]

  sendGroupMessage(ws, group_id, message)
  console.log(`[Welcome] 新成员 ${user_id} 加入群 ${group_id}，已发送欢迎`)
}
