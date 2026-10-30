"""端到端验证：模拟 FSD 服务器 → FSD9Client → ATC INFO 卡片（临时，可删除）。

流程：
  1. 模拟服务器发 $CH 挑战
  2. 验证客户端 $SA 的 HMAC 与服务器算法一致
  3. 服务器推送 #AA（管制上线）+ $AX（ATIS）
  4. 客户端应触发 controller:add / controller:atis，且 atis 正确
  5. 用 main.build_controller_card 生成上线卡片，确认包含 ATC INFO
"""
import asyncio
import hashlib
import hmac
import socket
import threading
import time

# 用测试地址/端口（避免连到真实服务器）
import py.config as config
config.FSD_HOST = '127.0.0.1'
config.FSD_PORT = 6901

from py.fsd9 import FSD9Client
from py.main import build_controller_card

CHALLENGE = 'a1b2c3d4e5f60718293a4b5c6d7e8f901a2b3c4d5e6f708192a3b4c5d6e7f8091'
PASSWORD = ''  # 口令从环境变量 FSD_BOT_PASSWORD 读取


def expected_hmac():
    pwd_hash = hashlib.sha256(PASSWORD.encode()).digest()
    return hmac.new(CHALLENGE.encode(), pwd_hash, hashlib.sha256).hexdigest()


def mock_server(result):
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', 6901))
    srv.listen(1)
    conn, _ = srv.accept()
    conn.settimeout(5)
    try:
        conn.sendall(('$CH' + CHALLENGE + '\r\n').encode())
        data = b''
        while b'\r\n' not in data:
            data += conn.recv(4096)
        line = data.decode(errors='replace').split('\r\n')[0]
        result['auth_line'] = line
        if line.startswith('$SA'):
            parts = line[3:].split(':')
            result['hmac_ok'] = len(parts) >= 4 and parts[3] == expected_hmac()
        # 推送管制上线（不广播 $AX）
        conn.sendall(b'#AAZBAA_TWR::Test Controller:12345:***:5:9\r\n')
        # 等待客户端 $AR 主动请求，再以 $AX 应答（验证主动拉取链路）
        req = b''
        try:
            conn.settimeout(3)
            while b'\r\n' not in req:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                req += chunk
        except socket.timeout:
            pass
        result['req'] = req.decode(errors='replace').strip()
        conn.sendall(b'$AXZBAA_TWR:*:ZBAA TWR 118.500^RWY 36L IN USE^QNH 1013\r\n')
        time.sleep(1.0)
    finally:
        conn.close()
        srv.close()


async def main():
    result = {}
    threading.Thread(target=mock_server, args=(result,), daemon=True).start()
    # 等 mock 服务器完成 bind/listen，避免连接被拒的竞态
    await asyncio.sleep(0.5)

    client = FSD9Client()
    client.callsign = 'CW-BOT'
    client.cid = '0000'
    client.password = PASSWORD

    add_event = asyncio.Event()
    atis_event = asyncio.Event()
    seen = {}

    def on_add(ctrl):
        seen['add'] = ctrl
        print('EVENT controller:add', ctrl.get('callsign'))
        add_event.set()

    def on_atis(payload):
        seen['atis'] = payload
        print('EVENT controller:atis', payload)
        atis_event.set()

    client.on('controller:add', on_add)
    client.on('controller:atis', on_atis)

    await client.start()
    try:
        await asyncio.wait_for(add_event.wait(), timeout=8)
        await asyncio.wait_for(atis_event.wait(), timeout=8)
    except asyncio.TimeoutError:
        print('TIMEOUT: 未收到事件')
    finally:
        await client.disconnect()

    print('\n===== 结果 =====')
    print('收到的 $SA 行:', result.get('auth_line', '')[:60], '...')
    print('HMAC 与服务器算法一致:', result.get('hmac_ok'))
    print('ATIS 原文:', repr(seen.get('atis', {}).get('atis')))

    # 生成上线卡片，确认含 ATC INFO
    ctrl = seen.get('add') or {}
    if ctrl:
        card = build_controller_card(ctrl, 'online')
        print('\n===== 上线卡片 =====')
        print(card)
        print('\n含 ATC INFO:', 'ATC INFO' in card)
        print('含 ATIS 首行:', 'ZBAA TWR 118.500' in card)


asyncio.run(main())
print('E2E ATIS TEST DONE')
