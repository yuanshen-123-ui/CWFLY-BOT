/**
 * OneBot 11 协议工具函数
 */

import crypto from 'crypto'

/**
 * 发送群消息
 * @param {import('ws').WebSocket} ws
 * @param {number|string} groupId
 * @param {string|object|Array} message
 */
export function sendGroupMessage(ws, groupId, message) {
  ws.send(JSON.stringify({
    action: 'send_group_msg',
    params: { group_id: Number(groupId), message },
    echo: crypto.randomUUID()
  }))
}

/**
 * 发送私聊消息
 * @param {import('ws').WebSocket} ws
 * @param {number|string} userId
 * @param {string|object|Array} message
 */
export function sendPrivateMessage(ws, userId, message) {
  ws.send(JSON.stringify({
    action: 'send_private_msg',
    params: { user_id: Number(userId), message },
    echo: crypto.randomUUID()
  }))
}

/**
 * 上传群文件
 * @param {import('ws').WebSocket} ws
 * @param {number|string} groupId
 * @param {string} filePath - 绝对路径
 * @param {string} fileName
 */
export function uploadGroupFile(ws, groupId, filePath, fileName) {
  ws.send(JSON.stringify({
    action: 'upload_group_file',
    params: {
      group_id: Number(groupId),
      file: filePath.replace(/\\/g, '/'),
      name: fileName
    },
    echo: crypto.randomUUID()
  }))
}

/**
 * 处理群加入请求（通过 / 拒绝）
 * @param {import('ws').WebSocket} ws
 * @param {string} flag - 请求标识（来自 request 事件的 flag 字段）
 * @param {string} subType - 'add'（主动加群）或 'invite'（被邀请）
 * @param {boolean} approve
 * @param {string} reason - 拒绝时的理由（approve=true 时可不填）
 */
export function setGroupAddRequest(ws, flag, subType, approve, reason = '') {
  ws.send(JSON.stringify({
    action: 'set_group_add_request',
    params: {
      flag,
      sub_type: subType,
      approve,
      reason
    },
    echo: crypto.randomUUID()
  }))
}

/**
 * 构造纯文本消息段
 * @param {string} text
 * @returns {Array}
 */
export function textMessage(text) {
  return [{ type: 'text', data: { text } }]
}
