"""FSD9 协议直连客户端（asyncio 版）。

通过 FSD9 TCP 协议直接连接 FSD 服务器，获取实时在线数据。
比 HTTP API 更实时、更可靠。

协议流程：
   连接 → 收到 $CH 挑战 → 发送 $SA 安全认证 → 收到 MOTD → 维护客户端列表
   或：连接 → 发送 #AP 明文认证 → 收到 MOTD → 维护客户端列表

消息处理：
   服务端推送 ADDCLIENT → 加入列表
   服务端推送 RMCLIENT → 移除列表
   服务端推送 位置更新 → 更新列表
   服务端推送 PONG    → 确认存活

事件（emit）：
   ready / controller:add / controller:remove / controller:atis /
   pilot:add / pilot:remove / client:remove
"""
import asyncio
import hashlib
import hmac
import time

from . import config

CL_CMD = {
    'ADDATC': '#AA',
    'ADDPILOT': '#AP',
    'RMATC': '#DA',
    'RMPILOT': '#DP',
    'MESSAGE': '#TM',
    'PILOTPOS': '@',
    'ATCPOS': '%',
    'PING': '$PI',
    'PONG': '$PO',
    'PLAN': '$FP',
    'CQ': '$CQ',
    'CR': '$CR',
    'KILL': '$!!',
    'ERROR': '$ER',
    'SECUREAUTH': '$SA',
    'CHALLENGE': '$CH',
    'ATISREQ': '$AR',
    'ATISDATA': '$AX',
}

CLIENT_PILOT = 1
CLIENT_ATC = 2
NEED_REVISION = 9

RECONNECT_DELAY = 10
PING_INTERVAL = 15
PING_TIMEOUT = 30


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_client_add_line(raw, atc):
    """解析 #AA/#AP 新增客户端行。返回 dict 或 None。"""
    payload = raw[3:] if raw.startswith('#AA') or raw.startswith('#AP') else raw
    parts = payload.split(':')
    if not parts:
        return None

    if atc:
        callsign = parts[0] or ''
        if not callsign:
            return None
        # EuroScope 格式: callsign:SERVER:cid:cid:password:rating:revision:simtype:...
        if len(parts) > 1 and parts[1].upper() == 'SERVER':
            cid = parts[2] or '0000'
            realname = parts[3] or parts[2] or callsign
            rating = _to_int(parts[5]) if len(parts) > 5 else None
        else:
            # 标准 FSD 格式: callsign::realname:cid:password:rating:revision
            realname = parts[2] or parts[1] or callsign
            cid = parts[3] or parts[2] or '0000'
            rating = _to_int(parts[4]) if len(parts) > 4 else None
        if rating is None or not (0 <= rating <= 20):
            rating = 0
            for i in range(1, len(parts)):
                v = _to_int(parts[i])
                if v is not None and 0 <= v <= 20:
                    rating = v
                    break
        return {'callsign': callsign, 'cid': cid, 'realname': realname,
                'rating': rating if rating is not None else 0, 'type': 'ATC'}

    callsign = parts[0] or ''
    if not callsign:
        return None
    cid = parts[2] or parts[3] or '0000'
    rating = 0
    for candidate in (parts[4] if len(parts) > 4 else '',
                      parts[3] if len(parts) > 3 else '',
                      parts[5] if len(parts) > 5 else ''):
        v = _to_int(candidate)
        if v is not None and 0 <= v <= 20:
            rating = v
            break
    realname = parts[6] if len(parts) > 6 else (parts[7] if len(parts) > 7 else callsign)
    return {'callsign': callsign, 'cid': cid, 'realname': realname,
            'rating': rating, 'type': 'PILOT'}


class FSD9Client:
    """维护持久连接和在线列表的 FSD9 客户端。"""

    def __init__(self):
        self.reader = None
        self.writer = None
        self._buffer = ''
        self.connected = False
        self.authenticated = False
        self.challenge = ''

        self.callsign = config.FSD_BOT_CALLSIGN
        self.cid = config.FSD_BOT_CID
        self.password = config.FSD_BOT_PASSWORD

        self.pilots = {}        # 大写呼号 -> client dict
        self.controllers = {}   # 大写呼号 -> client dict
        self._pending_atis = {}  # 大写呼号 -> raw atis 文本（ATIS 先于 #AA 到达时暂存）

        self._listeners = {}
        self._run_task = None
        self._ping_task = None
        self._last_pong = time.time()

    # ---------- 事件 ----------
    def on(self, event, callback):
        self._listeners.setdefault(event, []).append(callback)

    def emit(self, event, *args):
        for cb in self._listeners.get(event, []):
            try:
                loop = asyncio.get_event_loop()
                if asyncio.iscoroutinefunction(cb):
                    if loop.is_running():
                        asyncio.ensure_future(cb(*args))
                    else:
                        loop.run_until_complete(cb(*args))
                else:
                    cb(*args)
            except Exception as e:
                print(f'[FSD9] listener error ({event}): {e}')

    # ---------- 生命周期 ----------
    async def start(self):
        self._run_task = asyncio.create_task(self._run_forever())

    async def _run_forever(self):
        while True:
            try:
                await self._connect_once()
            except Exception as e:
                print(f'[FSD9] error({type(e).__name__}): {e}')
            await asyncio.sleep(RECONNECT_DELAY)

    async def _connect_once(self):
        self._last_pong = time.time()
        self.reader, self.writer = await asyncio.open_connection(
            config.FSD_HOST, config.FSD_PORT)
        self.connected = True
        print(f'[FSD9] Connected to {config.FSD_HOST}:{config.FSD_PORT}')
        self._buffer = ''
        try:
            while True:
                data = await self.reader.read(65536)
                if not data:
                    break
                self._buffer += data.decode('utf-8', errors='replace')
                while '\r\n' in self._buffer:
                    idx = self._buffer.index('\r\n')
                    line = self._buffer[:idx]
                    self._buffer = self._buffer[idx + 2:]
                    if line:
                        self._process_line(line)
        finally:
            self.connected = False
            self.authenticated = False
            try:
                self.writer.close()
            except Exception:
                pass
            print('[FSD9] Connection closed')

    async def disconnect(self):
        self.connected = False
        self.authenticated = False
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None
        if self.writer:
            try:
                self.writer.close()
            except Exception:
                pass
            self.writer = None

    # ---------- 发送 ----------
    def _send(self, raw):
        if self.writer and self.connected:
            try:
                self.writer.write((raw + '\r\n').encode('latin-1'))
                asyncio.ensure_future(self.writer.drain())
            except Exception:
                pass

    # ---------- 协议处理 ----------
    def _process_line(self, line):
        if line.startswith(CL_CMD['CHALLENGE']):
            self.challenge = line[3:]
            self._send_auth()
            return
        if line.startswith(CL_CMD['ERROR']):
            parts = line[3:].split(':')
            if len(parts) > 2 and parts[2] == '006':
                print('[FSD9] Auth failed (invalid CID/password)')
            return
        if line.startswith(CL_CMD['ADDATC']):
            self._add_client(line[3:], CLIENT_ATC)
            return
        if line.startswith(CL_CMD['ADDPILOT']):
            self._add_client(line[3:], CLIENT_PILOT)
            return
        if line.startswith(CL_CMD['RMATC']) or line.startswith(CL_CMD['RMPILOT']):
            self._remove_client(line[3:])
            return
        if line.startswith(CL_CMD['PILOTPOS']):
            self._update_pilot_pos(line[1:])
            return
        if line.startswith(CL_CMD['ATCPOS']):
            self._update_atc_pos(line[1:])
            return
        if line.startswith(CL_CMD['PLAN']):
            self._update_flight_plan(line[3:])
            return
        if line.startswith(CL_CMD['PONG']):
            self._last_pong = time.time()
            return
        if line.startswith(CL_CMD['CR']):
            # 解析 CQ 响应（如个人信息等）
            return
        if line.startswith(CL_CMD['ATISDATA']):
            self._update_atis(line[3:])
            return

    def _send_auth(self):
        if self.challenge:
            # 安全认证 $SA：与服务器算法一致
            #   pwd_hash = sha256(password bytes)
            #   hmac key = challenge 十六进制字符串本身（encode()，非 hex 解码！）
            pwd_hash = hashlib.sha256(self.password.encode()).digest()
            digest = hmac.new(self.challenge.encode(), pwd_hash,
                              hashlib.sha256).hexdigest()
            self._send(f'{CL_CMD["SECUREAUTH"]}{self.callsign}:{CLIENT_PILOT}:'
                       f'{self.cid}:{digest}:1:{NEED_REVISION}:{self.callsign}:0')
        else:
            # 安全(2026-10-25 审计 P1-1): 移除明文密码后备, 无挑战即中止
            raise RuntimeError('FSD server did not send $CH challenge, '
                               'aborting (no plaintext auth)')
        # 标记认证完成（MOTD 后将收到现有客户端列表）
        asyncio.get_event_loop().call_later(2.0, self._mark_authenticated)

    def _mark_authenticated(self):
        self.authenticated = True
        self.emit('ready')
        self._start_ping()

    def _start_ping(self):
        if self._ping_task:
            self._ping_task.cancel()
        self._ping_task = asyncio.create_task(self._ping_loop())

    async def _ping_loop(self):
        while True:
            await asyncio.sleep(PING_INTERVAL)
            if not self.connected:
                continue
            self._send(f'{CL_CMD["PING"]}{self.callsign}:*')
            if time.time() - self._last_pong > PING_TIMEOUT:
                print('[FSD9] Ping timeout, reconnecting...')
                await self.disconnect()

    # ---------- 客户端列表维护 ----------
    def _add_client(self, raw, atc):
        parsed = parse_client_add_line(raw, atc)
        if not parsed:
            return
        now = time.time()
        client = {
            'callsign': parsed['callsign'],
            'cid': parsed['cid'],
            'realname': parsed['realname'],
            'rating': parsed['rating'],
            'type': parsed['type'],
            'frequency': 0,
            'facilitytype': 0,
            'visualrange': 40,
            'lat': 0.0, 'lon': 0.0, 'altitude': 0, 'groundspeed': 0,
            'transponder': 0,
            'plan': None,
            'starttime': int(now),
            'lastSeen': now,
            'atis': '',
        }
        if atc == CLIENT_ATC:
            key = parsed['callsign'].upper()
            is_new = key not in self.controllers
            # 应用可能先到的待匹配 ATIS（刚上线时 ATIS 先于 #AA 到达）
            if key in self._pending_atis:
                client['atis'] = self._pending_atis.pop(key).replace('^', '\n').strip()
            self.controllers[key] = client
            if is_new:
                print(f'[FSD9] controller:add {key} (cid={client["cid"]})')
                # 主动请求 ATIS（$AR）——服务器以 $AX 应答，补强广播可能丢失的时序
                self._send(f'{CL_CMD["ATISREQ"]}{self.callsign}:{key}')
                self.emit('controller:add', client)
        else:
            key = parsed['callsign'].upper()
            is_new = key not in self.pilots
            self.pilots[key] = client
            if is_new:
                self.emit('pilot:add', client)

    def _remove_client(self, raw):
        callsign = raw.split(':')[0]
        key = callsign.upper()
        ctrl = self.controllers.get(key)
        pilot = self.pilots.get(key)
        self.pilots.pop(key, None)
        self.controllers.pop(key, None)
        self.emit('client:remove', callsign)
        if ctrl:
            print(f'[FSD9] controller:remove {key}')
            self.emit('controller:remove', ctrl)
        elif pilot:
            self.emit('pilot:remove', pilot)

    def _update_pilot_pos(self, raw):
        # @格式: identflag:callsign:transponder:rating:lat:lon:alt:gs:pbh:flags
        parts = raw.split(':')
        if len(parts) < 7:
            return
        key = parts[1].upper() if parts[1] else ''
        pilot = self.pilots.get(key)
        if not pilot:
            return
        pilot['transponder'] = _to_int(parts[2]) or 0
        pilot['lat'] = self._to_float(parts[4])
        pilot['lon'] = self._to_float(parts[5])
        pilot['altitude'] = _to_int(parts[6]) or 0
        pilot['groundspeed'] = _to_int(parts[7]) if len(parts) > 7 else 0
        pilot['lastSeen'] = time.time()

    def _update_atc_pos(self, raw):
        # %格式(去掉%后): callsign:frequency:facilitytype:visualrange:rating:lat:lon:alt
        parts = raw.split(':')
        if len(parts) < 8:
            return
        key = parts[0].upper() if parts[0] else ''
        ctrl = self.controllers.get(key)
        if not ctrl:
            return
        ctrl['frequency'] = _to_int(parts[1]) or 0
        ctrl['facilitytype'] = _to_int(parts[2]) or 0
        ctrl['visualrange'] = _to_int(parts[3]) or 40
        ctrl['lat'] = self._to_float(parts[5])
        ctrl['lon'] = self._to_float(parts[6])
        ctrl['altitude'] = _to_int(parts[7]) or 0
        ctrl['lastSeen'] = time.time()

    def _update_atis(self, raw):
        # $AX格式: from:to:data 或 from:data（多行用 ^ 分隔）
        parts = raw.split(':')
        if not parts:
            return
        callsign = parts[0]
        key = callsign.upper()
        ctrl = self.controllers.get(key)
        data = ':'.join(parts[2:]) if len(parts) >= 3 else ':'.join(parts[1:])
        if not ctrl:
            # ATIS 可能来自尚未登记的管制员（如刚上线），此时存入待匹配
            self._pending_atis[key] = data
            return
        ctrl['atis'] = data.replace('^', '\n').strip()
        print(f'[FSD_ATIS] 收到 {callsign} ATIS: {data.replace("^", " ")[:60]}...')
        self.emit('controller:atis', {'callsign': callsign, 'atis': ctrl['atis']})

    def _update_flight_plan(self, raw):
        # $FP格式: callsign:type:aircraft:tascruise:dep:deptime:actdep:alt:dest:...
        parts = raw.split(':')
        if len(parts) < 4:
            return
        key = parts[0].upper() if parts[0] else ''
        client = self.pilots.get(key) or self.controllers.get(key)
        if not client:
            return
        client['plan'] = {
            'type': parts[1][0] if len(parts) > 1 and parts[1] else 'I',
            'aircraft': parts[2] if len(parts) > 2 else '',
            'tascruise': _to_int(parts[3]) or 0,
            'depairport': parts[4] if len(parts) > 4 else '',
            'deptime': _to_int(parts[5]) or 0,
            'actdeptime': _to_int(parts[6]) or 0,
            'altitude': parts[7] if len(parts) > 7 else '',
            'destairport': parts[8] if len(parts) > 8 else '',
            'hrsenroute': _to_int(parts[9]) or 0,
            'minenroute': _to_int(parts[10]) or 0,
            'hrsfuel': _to_int(parts[11]) or 0,
            'minfuel': _to_int(parts[12]) or 0,
            'altairport': parts[13] if len(parts) > 13 else '',
            'remarks': parts[14] if len(parts) > 14 else '',
            'route': parts[15] if len(parts) > 15 else '',
        }

    def query_client(self, callsign):
        """通过 $CQ 查询某个客户端的详细信息。"""
        self._send(f'{CL_CMD["CQ"]}{self.callsign}:{callsign}:RN')

    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    # ---------- 公开 API ----------
    def get_pilot(self, callsign):
        return self.pilots.get(str(callsign).upper())

    def get_controller(self, callsign):
        return self.controllers.get(str(callsign).upper())

    @property
    def online_pilot_count(self):
        return len(self.pilots)

    @property
    def online_controller_count(self):
        return len(self.controllers)

    @property
    def pilot_list(self):
        return list(self.pilots.values())

    @property
    def controller_list(self):
        return list(self.controllers.values())

    @property
    def is_ready(self):
        return self.connected and self.authenticated


# ========== 单例 ==========
_instance = None
_start_lock = asyncio.Lock()


def get_fsd9_client():
    global _instance
    if _instance is None:
        _instance = FSD9Client()
    return _instance


async def ensure_fsd9_started():
    """确保单例已启动（幂等，供主入口调用）。"""
    global _instance
    client = get_fsd9_client()
    if client._run_task is None:
        await client.start()
    return client
