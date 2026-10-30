/**
 * 群入群申请自动审核（直连主站数据库版）
 *
 * 流程：
 *   1. 收到 OneBot request 事件（request_type=group, sub_type=add）
 *   2. 读取申请人填写的申请内容（event.comment）
 *   3. 直连 MySQL（与主站/fsd-py 共用 User 表），校验内容是否匹配注册用户
 *      （CID / 注册邮箱 / 用户名 任一项相同即视为匹配）
 *   4. 匹配 → 调用 set_group_add_request 自动通过；不匹配 → 不做任何处理（留给管理员人工审核）
 *
 * 说明：不依赖主站 API（主站由其他同学维护），数据库连接配置见 bot/.env：
 *   DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME
 */

import mysql from 'mariadb'
import { setGroupAddRequest } from '../utils/onebot.js'

let pool = null

function getPool() {
  if (!pool) {
    pool = mysql.createPool({
      host: process.env.DB_HOST || '127.0.0.1',
      port: Number(process.env.DB_PORT || 3306),
      user: process.env.DB_USER || 'root',
      password: process.env.DB_PASSWORD || '',
      database: process.env.DB_NAME || 'cwfly',
      connectionLimit: 5,
      charset: 'utf8mb4',
    })
  }
  return pool
}

/** 可自动审核的群号集合；空集合表示所有群都启用 */
function getAutoApproveGroups() {
  const raw = process.env.AUTO_APPROVE_GROUP_IDS || ''
  return new Set(raw.split(',').map(s => String(s).trim()).filter(Boolean))
}

/**
 * 在申请内容中查找平台注册用户身份。
 * 匹配规则（MySQL utf8mb4_unicode_ci 下字符串等值比较即大小写不敏感）：
 *   ① 整段内容精确等于 某个 CID / 邮箱 / 用户名
 *   ② 从内容中提取 token 逐个匹配：
 *      - 含 @ 的 token      → 邮箱
 *      - 纯数字 token（3-6位）→ CID
 *      - 其他 token（>=2字符）→ 用户名
 * 返回 { field: 'cid'|'email'|'username', cid } 或 null
 */
async function findIdentity(text) {
  const raw = String(text || '').trim()
  if (!raw) return null
  const lower = raw.toLowerCase()

  const conn = await getPool().getConnection()
  try {
    // ① 整段内容精确匹配（参数化查询防注入）
    const rows = await conn.query(
      'SELECT cid, username, email FROM `User` WHERE cid = ? OR username = ? OR email = ? LIMIT 1',
      [raw, lower, lower]
    )
    if (rows && rows.length) {
      const u = rows[0]
      if (u.cid === raw) return { field: 'cid', cid: u.cid }
      if (String(u.email || '').toLowerCase() === lower) return { field: 'email', cid: u.cid }
      return { field: 'username', cid: u.cid }
    }

    // ② 提取 token 逐个匹配（覆盖 "我的CID是0000" / "邮箱 xxx@yyy.com" 等写法）
    const tokens = lower.match(
      /[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}|\d{3,6}|[a-z0-9_]{2,}|[\u4e00-\u9fa5]{2,}/g
    ) || []
    const seen = new Set()
    for (const token of tokens) {
      if (seen.has(token)) continue
      seen.add(token)

      if (token.includes('@')) {
        const r = await conn.query('SELECT cid FROM `User` WHERE email = ? LIMIT 1', [token])
        if (r && r.length) return { field: 'email', cid: String(r[0].cid) }
      } else if (/^\d{3,6}$/.test(token)) {
        const r = await conn.query('SELECT cid FROM `User` WHERE cid = ? LIMIT 1', [token])
        if (r && r.length) return { field: 'cid', cid: String(r[0].cid) }
      } else if (token.length >= 2) {
        const r = await conn.query('SELECT cid FROM `User` WHERE username = ? LIMIT 1', [token])
        if (r && r.length) return { field: 'username', cid: String(r[0].cid) }
      }
    }
    return null
  } finally {
    conn.release()
  }
}

/**
 * 处理群入群申请事件
 * @param {import('ws').WebSocket} ws
 * @param {object} event - OneBot request 事件
 */
export async function handleGroupRequest(ws, event) {
  // 仅处理「主动加群」申请；被邀请（invite）不做自动处理
  if (event.sub_type !== 'add') return

  const groupId = String(event.group_id || '')
  const userId = String(event.user_id || '')
  const flag = String(event.flag || '')
  const comment = String(event.comment || '').trim()

  if (!groupId || !userId || !flag) return

  // 群白名单过滤
  const allowed = getAutoApproveGroups()
  if (allowed.size > 0 && !allowed.has(groupId)) return

  // 未填写申请内容 → 无法校验，不做处理
  if (!comment) {
    console.log(`[GroupRequest] 申请无内容，跳过: QQ=${userId} 群=${groupId}`)
    return
  }

  let hit
  try {
    hit = await findIdentity(comment)
  } catch (err) {
    console.error(`[GroupRequest] 数据库查询失败: QQ=${userId} 群=${groupId}: ${err.message}`)
    return
  }

  if (hit) {
    const reason = `CW 平台注册用户（${hit.field}: ${hit.cid}）`
    setGroupAddRequest(ws, flag, 'add', true, reason)
    console.log(`[GroupRequest] ✅ 自动通过: QQ=${userId} 群=${groupId} 匹配(${hit.field}:${hit.cid}) 内容="${comment}"`)
  } else {
    // 未匹配到注册用户 → 不做处理，等待管理员人工审核
    console.log(`[GroupRequest] 未匹配注册用户，跳过: QQ=${userId} 群=${groupId} 内容="${comment}"`)
  }
}
