/**
 * FSD9 协议直连客户端
 *
 * 通过 FSD9 TCP 协议直接连接 FSD 服务器，获取实时在线数据。
 * 比 HTTP API 更实时、更可靠。
 *
 * 协议流程：
 *   连接 → 收到 $CH 挑战 → 发送 $SA 安全认证 → 收到 MOTD → 维护客户端列表
 *   或：连接 → 发送 #AP 明文认证 → 收到 MOTD → 维护客户端列表
 *
 * 消息处理：
 *   服务端推送 ADDCLIENT → 加入列表
 *   服务端推送 RMCLIENT → 移除列表
 *   服务端推送 位置更新 → 更新列表
 *   服务端推送 PONG → 确认存活
 */

import { EventEmitter } from 'events'
import { connect } from 'net'
import crypto from 'crypto'

const FSD_HOST = process.env.FSD_HOST || '127.0.0.1'
const FSD_PORT = Number(process.env.FSD_PORT || 6809)
const FSD9_API_URL = process.env.FSD_API_URL || 'http://127.0.0.1:8080/api'

/** FSD9 协议常量 */
const CL_CMD = {
  ADDATC: '#AA',
  ADDPILOT: '#AP',
  RMATC: '#DA',
  RMPILOT: '#DP',
  MESSAGE: '#TM',
  PILOTPOS: '@',
  ATCPOS: '%',
  PING: '$PI',
  PONG: '$PO',
  PLAN: '$FP',
  CQ: '$CQ',
  CR: '$CR',
  KILL: '$!!',
  ERROR: '$ER',
  SECUREAUTH: '$SA',
  CHALLENGE: '$CH',
  ATISREQ: '$AR',   // 请求 ATIS
  ATISDATA: '$AX',  // ATIS 数据/发布
}

const CLIENT_PILOT = 1
const CLIENT_ATC = 2
const NEED_REVISION = 9

function parseClientAddLine(raw, type) {
  const payload = raw.startsWith('#AA') || raw.startsWith('#AP') ? raw.slice(3) : raw
  const parts = payload.split(':')
  if (!parts.length) return null

  if (type === CLIENT_ATC) {
    const callsign = parts[0] || ''
    if (!callsign) return null
    const realname = parts[2] || parts[1] || callsign
    const cid = parts[3] || parts[2] || '0000'
    // #AA格式: callsign::realname:cid:rating:protocol → rating在parts[4]
    const ratingCandidates = [parts[4], parts[3], parts[5]]
    let rating = 0
    for (const candidate of ratingCandidates) {
      const value = Number(candidate)
      if (Number.isFinite(value) && value >= 0 && value <= 20) {
        rating = value
        break
      }
    }
    return { callsign, cid, realname, rating, type: 'ATC' }
  }

  const callsign = parts[0] || ''
  if (!callsign) return null
  const cid = parts[2] || parts[3] || '0000'
  const ratingCandidates = [parts[4], parts[3], parts[5]]
  let rating = 0
  for (const candidate of ratingCandidates) {
    const value = Number(candidate)
    if (Number.isFinite(value) && value >= 0 && value <= 20) {
      rating = value
      break
    }
  }
  const realname = parts[6] || parts[7] || callsign
  return { callsign, cid, realname, rating, type: 'PILOT' }
}

export { parseClientAddLine }

/**
 * FSD9 客户端 — 维护持久连接和在线列表
 */
class FSD9Client extends EventEmitter {
  constructor() {
    super()
    this.socket = null
    this.buffer = ''
    this.connected = false
    this.authenticated = false
    this.challenge = ''
    this.callsign = process.env.FSD_BOT_CALLSIGN || 'CW-BOT'
    this.cid = process.env.FSD_BOT_CID || '000001'
    this.password = process.env.FSD_BOT_PASSWORD || ''

    /** @type {Map<string, object>} */
    this.pilots = new Map()
    /** @type {Map<string, object>} */
    this.controllers = new Map()

    this.pingInterval = null
    this.reconnectTimer = null
    this._lastPong = Date.now()
  }

  /**
   * 连接并认证到 FSD 服务器
   */
  connect() {
    if (this.socket) this.disconnect()
    // 重置 ping 超时基准，避免复用单例时陈旧 _lastPong 导致误判超时断开
    this._lastPong = Date.now()

    this.socket = connect({ host: FSD_HOST, port: FSD_PORT }, () => {
      console.log(`[FSD9] Connected to ${FSD_HOST}:${FSD_PORT}`)
      this.connected = true
    })

    this.socket.on('data', (data) => this._onData(data))
    this.socket.on('close', () => this._onClose())
    this.socket.on('error', (err) => {
      console.error(`[FSD9] Socket error: ${err.message}`)
      this._scheduleReconnect()
    })

    this.socket.setTimeout(60000)
    this.socket.on('timeout', () => {
      console.warn('[FSD9] Timeout, reconnecting...')
      this.disconnect()
      this._scheduleReconnect()
    })
  }

  disconnect() {
    this.connected = false
    this.authenticated = false
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
    if (this.socket) {
      try { this.socket.destroy() } catch {}
      this.socket = null
    }
  }

  _scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      console.log('[FSD9] Reconnecting...')
      this.connect()
    }, 10000)
  }

  /** 发送原始数据 */
  _send(raw) {
    if (this.socket && this.connected) {
      try { this.socket.write(raw + '\r\n') } catch {}
    }
  }

  /** 接收数据行 */
  _onData(data) {
    this.buffer += data.toString('utf-8')
    while (this.buffer.includes('\r\n')) {
      const idx = this.buffer.indexOf('\r\n')
      const line = this.buffer.slice(0, idx)
      this.buffer = this.buffer.slice(idx + 2)
      if (line) this._processLine(line)
    }
  }

  _onClose() {
    console.log('[FSD9] Connection closed')
    this.connected = false
    this.authenticated = false
    this._scheduleReconnect()
  }

  /** 处理一行协议 */
  _processLine(line) {
    // $CH<64hex> — 挑战
    if (line.startsWith(CL_CMD.CHALLENGE)) {
      this.challenge = line.slice(3)
      this._sendAuth()
      return
    }

    // $ER — 错误
    if (line.startsWith(CL_CMD.ERROR)) {
      const parts = line.slice(3).split(':')
      const errCode = parts[2]
      if (errCode === '006') {
        console.warn('[FSD9] Auth failed (invalid CID/password)')
      }
      return
    }

    // #AA / #AP — 新客户端上线
    if (line.startsWith(CL_CMD.ADDATC)) {
      this._addClient(line.slice(3), CLIENT_ATC)
      return
    }
    if (line.startsWith(CL_CMD.ADDPILOT)) {
      this._addClient(line.slice(3), CLIENT_PILOT)
      return
    }

    // #DA / #DP — 客户端下线
    if (line.startsWith(CL_CMD.RMATC) || line.startsWith(CL_CMD.RMPILOT)) {
      this._removeClient(line.slice(3))
      return
    }

    // @ — 飞行员位置更新
    if (line.startsWith(CL_CMD.PILOTPOS)) {
      this._updatePilotPos(line.slice(1))
      return
    }

    // % — 管制员位置更新
    if (line.startsWith(CL_CMD.ATCPOS)) {
      this._updateAtcPos(line.slice(1))
      return
    }

    // $FP — 飞行计划
    if (line.startsWith(CL_CMD.PLAN)) {
      this._updateFlightPlan(line.slice(3))
      return
    }

    // $PO — Pong
    if (line.startsWith(CL_CMD.PONG)) {
      this._lastPong = Date.now()
      return
    }

    // $CR — CQ 响应
    if (line.startsWith(CL_CMD.CR)) {
      // 解析 CQ 响应（如个人信息等）
      return
    }

    // $AX — ATIS 数据（管制员发布的航站情报）
    if (line.startsWith(CL_CMD.ATISDATA)) {
      this._updateAtis(line.slice(3))
      return
    }
  }

  /** 发送认证 */
  _sendAuth() {
    if (this.challenge) {
      // 安全认证 $SA
      const pwdHash = crypto.createHash('sha256').update(this.password).digest()
      const hmac = crypto.createHmac('sha256', this.challenge).update(pwdHash).digest('hex')
      this._send(`${CL_CMD.SECUREAUTH}${this.callsign}:${CLIENT_PILOT}:${this.cid}:${hmac}:1:${NEED_REVISION}:${this.callsign}:0`)
    } else {
      // 明文认证 #AP（后备）
      this._send(`${CL_CMD.ADDPILOT}${this.callsign}:${CLIENT_PILOT}:${this.cid}:${this.password}:1:${NEED_REVISION}:0:${this.callsign}`)
    }
    // 标记认证完成（MOTD 后将收到现有客户端列表）
    setTimeout(() => {
      this.authenticated = true
      this.emit('ready')
      this._startPing()
    }, 2000)
  }

  _startPing() {
    if (this.pingInterval) clearInterval(this.pingInterval)
    this.pingInterval = setInterval(() => {
      this._send(`${CL_CMD.PING}${this.callsign}:*`)
      // 检查上次 pong 是否超时（30 秒）
      if (Date.now() - this._lastPong > 30000) {
        console.warn('[FSD9] Ping timeout, reconnecting...')
        this.disconnect()
        this._scheduleReconnect()
      }
    }, 15000)
  }

  /** 解析并添加客户端 */
  _addClient(raw, type) {
    const parsed = parseClientAddLine(raw, type)
    if (!parsed) return

    const client = {
      callsign: parsed.callsign,
      cid: parsed.cid,
      realname: parsed.realname,
      rating: parsed.rating,
      type: parsed.type,
      frequency: 0,
      facilitytype: 0,
      visualrange: 40,
      lat: 0, lon: 0, altitude: 0, groundspeed: 0,
      transponder: 0,
      plan: null,
      starttime: Math.floor(Date.now() / 1000),
      lastSeen: Date.now()
    }

    if (type === CLIENT_ATC) {
      const key = parsed.callsign.toUpperCase()
      const isNew = !this.controllers.has(key)
      // 应用可能先到的待匹配 ATIS（刚上线时 ATIS 先于 #AA 到达）
      if (this._pendingAtis?.has(key)) {
        const pending = this._pendingAtis.get(key)
        this._pendingAtis.delete(key)
        client.atis = pending.replace(/\^/g, '\n').trim()
      }
      this.controllers.set(key, client)
      if (isNew) {
        console.log(`[FSD9] controller:add ${key} (cid=${client.cid})`)
        this.emit('controller:add', client)
      }
    } else {
      const key = parsed.callsign.toUpperCase()
      const isNew = !this.pilots.has(key)
      this.pilots.set(key, client)
      if (isNew) this.emit('pilot:add', client)
    }
  }

  _removeClient(raw) {
    // #DA/#DP格式: callsign
    const callsign = raw.split(':')[0]
    const key = callsign.toUpperCase()
    const ctrl = this.controllers.get(key)
    const pilot = this.pilots.get(key)
    this.pilots.delete(key)
    this.controllers.delete(key)
    this.emit('client:remove', callsign)
    if (ctrl) {
      console.log(`[FSD9] controller:remove ${key}`)
      this.emit('controller:remove', ctrl)
    } else if (pilot) {
      this.emit('pilot:remove', pilot)
    }
  }

  _updatePilotPos(raw) {
    // @格式: identflag:callsign:transponder:rating:lat:lon:alt:gs:pbh:flags
    const parts = raw.split(':')
    if (parts.length < 7) return
    const callsign = parts[1]
    const key = callsign?.toUpperCase()
    const pilot = this.pilots.get(key)
    if (!pilot) return

    pilot.transponder = parseInt(parts[2]) || 0
    pilot.lat = parseFloat(parts[4]) || 0
    pilot.lon = parseFloat(parts[5]) || 0
    pilot.altitude = parseInt(parts[6]) || 0
    pilot.groundspeed = parseInt(parts[7]) || 0
    pilot.lastSeen = Date.now()
  }

  _updateAtcPos(raw) {
    // %格式(去掉%后): callsign:frequency:facilitytype:visualrange:rating:lat:lon:alt
    const parts = raw.split(':')
    if (parts.length < 8) return
    const callsign = parts[0]
    const key = callsign?.toUpperCase()
    const ctrl = this.controllers.get(key)
    if (!ctrl) return

    ctrl.frequency = parseInt(parts[1]) || 0
    ctrl.facilitytype = parseInt(parts[2]) || 0
    ctrl.visualrange = parseInt(parts[3]) || 40
    ctrl.lat = parseFloat(parts[5]) || 0
    ctrl.lon = parseFloat(parts[6]) || 0
    ctrl.altitude = parseInt(parts[7]) || 0
    ctrl.lastSeen = Date.now()
  }

  /** 处理 ATIS 数据（$AX） */
  _updateAtis(raw) {
    // $AX格式: from:to:data 或 from:data（多行用 ^ 分隔）
    const parts = raw.split(':')
    if (!parts.length) return
    const callsign = parts[0]
    const key = callsign?.toUpperCase()
    const ctrl = this.controllers.get(key)
    // ATIS 可能来自尚未登记的管制员（如刚上线），此时存入待匹配
    if (!ctrl) {
      if (!this._pendingAtis) this._pendingAtis = new Map()
      this._pendingAtis.set(key, parts.length >= 3 ? parts.slice(2).join(':') : parts.slice(1).join(':'))
      return
    }
    let data = parts.length >= 3 ? parts.slice(2).join(':') : parts.slice(1).join(':')
    ctrl.atis = data.replace(/\^/g, '\n').trim()
    this.emit('controller:atis', { callsign, atis: ctrl.atis })
  }

  _updateFlightPlan(raw) {
    // $FP格式: callsign:type:aircraft:tascruise:dep:deptime:actdep:alt:dest:...
    // 或来自于原始协议的不同格式
    const parts = raw.split(':')
    if (parts.length < 4) return
    const callsign = parts[0]
    const key = callsign?.toUpperCase()
    const client = this.pilots.get(key) || this.controllers.get(key)
    if (!client) return

    client.plan = {
      type: parts[1]?.[0] || 'I',
      aircraft: parts[2] || '',
      tascruise: parseInt(parts[3]) || 0,
      depairport: parts[4] || '',
      deptime: parseInt(parts[5]) || 0,
      actdeptime: parseInt(parts[6]) || 0,
      altitude: parts[7] || '',
      destairport: parts[8] || '',
      hrsenroute: parseInt(parts[9]) || 0,
      minenroute: parseInt(parts[10]) || 0,
      hrsfuel: parseInt(parts[11]) || 0,
      minfuel: parseInt(parts[12]) || 0,
      altairport: parts[13] || '',
      remarks: parts[14] || '',
      route: parts[15] || '',
    }
  }

  /** 通过 $CQ 查询某个客户端的详细信息 */
  queryClient(callsign) {
    this._send(`${CL_CMD.CQ}${this.callsign}:${callsign}:RN`)
  }

  // ========== 公开 API ==========

  getPilot(callsign) {
    return this.pilots.get(callsign.toUpperCase()) || null
  }

  getController(callsign) {
    return this.controllers.get(callsign.toUpperCase()) || null
  }

  get onlinePilotCount() {
    return this.pilots.size
  }

  get onlineControllerCount() {
    return this.controllers.size
  }

  get pilotList() {
    return Array.from(this.pilots.values())
  }

  get controllerList() {
    return Array.from(this.controllers.values())
  }

  get isReady() {
    return this.connected && this.authenticated
  }
}

// ========== 单例 ==========
let instance = null

export function getFSD9Client() {
  if (!instance) {
    instance = new FSD9Client()
    instance.connect()
  }
  return instance
}

export function disconnectFSD9() {
  if (instance) {
    instance.disconnect()
    instance = null
  }
}
