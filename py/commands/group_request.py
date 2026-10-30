"""群入群申请自动审核（直连主站数据库版）。

流程：
  1. 收到 OneBot request 事件（request_type=group, sub_type=add）
  2. 读取申请人填写的申请内容（event.comment）
  3. 直连 MySQL（与主站/fsd-py 共用 User 表），校验内容是否匹配注册用户
     （CID / 注册邮箱 / 用户名 任一项相同即视为匹配）
  4. 匹配 → 调用 set_group_add_request 自动通过；不匹配 → 不做任何处理（留给管理员人工审核）

说明：不依赖主站 API（主站由其他同学维护），数据库连接配置见 bot/.env：
  DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME
"""
import re

from .. import config, onebot


def _db_config():
    return {
        'host': config.env('DB_HOST', '127.0.0.1'),
        'port': int(config.env('DB_PORT', '3306')),
        'user': config.env('DB_USER', 'root'),
        'password': config.env('DB_PASSWORD', ''),
        'database': config.env('DB_NAME', 'cwfly'),
        'charset': 'utf8mb4',
    }


def _auto_approve_groups():
    """可自动审核的群号集合；空集合表示所有群都启用。"""
    raw = config.env('AUTO_APPROVE_GROUP_IDS', '')
    return {x.strip() for x in raw.split(',') if x.strip()}


def _find_identity(text):
    """在申请内容中查找平台注册用户身份（与 Node 版逻辑一致）。

    匹配规则（MySQL utf8mb4_unicode_ci 下等值比较大小写不敏感）：
      ① 整段内容精确等于 某个 CID / 邮箱 / 用户名
      ② 提取 token 逐个匹配：含 @ → 邮箱；纯数字(3-6位) → CID；其他(>=2字符) → 用户名
    返回 (field, cid) 或 None。
    """
    import pymysql

    raw = str(text or '').strip()
    if not raw:
        return None
    lower = raw.lower()

    conn = pymysql.connect(**_db_config())
    try:
        with conn.cursor() as cur:
            # ① 整段内容精确匹配（参数化查询防注入）
            cur.execute(
                'SELECT cid, username, email FROM `User` '
                'WHERE cid = %s OR username = %s OR email = %s LIMIT 1',
                (raw, lower, lower),
            )
            row = cur.fetchone()
            if row:
                cid, username, email = str(row[0]), str(row[1] or ''), str(row[2] or '')
                if cid == raw:
                    return ('cid', cid)
                if email.lower() == lower:
                    return ('email', cid)
                return ('username', cid)

            # ② 提取 token 逐个匹配
            tokens = re.findall(
                r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}|\d{3,6}|[a-z0-9_]{2,}|[\u4e00-\u9fa5]{2,}',
                lower,
            )
            seen = set()
            for token in tokens:
                if token in seen:
                    continue
                seen.add(token)

                if '@' in token:
                    cur.execute('SELECT cid FROM `User` WHERE email = %s LIMIT 1', (token,))
                elif re.fullmatch(r'\d{3,6}', token):
                    cur.execute('SELECT cid FROM `User` WHERE cid = %s LIMIT 1', (token,))
                elif len(token) >= 2:
                    cur.execute('SELECT cid FROM `User` WHERE username = %s LIMIT 1', (token,))
                else:
                    continue
                r = cur.fetchone()
                if r:
                    return ('email' if '@' in token else 'cid' if re.fullmatch(r'\d{3,6}', token) else 'username', str(r[0]))
            return None
    finally:
        conn.close()


async def handle_group_request(ws, event):
    """处理群入群申请事件。"""
    # 仅处理「主动加群」申请；被邀请（invite）不做自动处理
    if event.get('sub_type') != 'add':
        return

    group_id = str(event.get('group_id') or '')
    user_id = str(event.get('user_id') or '')
    flag = str(event.get('flag') or '')
    comment = str(event.get('comment') or '').strip()

    if not group_id or not user_id or not flag:
        return

    # 群白名单过滤
    allowed = _auto_approve_groups()
    if allowed and group_id not in allowed:
        return

    # 未填写申请内容 → 无法校验，不做处理
    if not comment:
        print(f'[GroupRequest] 申请无内容，跳过: QQ={user_id} 群={group_id}')
        return

    try:
        hit = await _find_identity_async(comment)
    except Exception as e:
        print(f'[GroupRequest] 数据库查询失败: QQ={user_id} 群={group_id}: {e}')
        return

    if hit:
        field, cid = hit
        reason = f'CW 平台注册用户（{field}: {cid}）'
        await onebot.set_group_add_request(ws, flag, 'add', True, reason)
        print(f'[GroupRequest] ✅ 自动通过: QQ={user_id} 群={group_id} 匹配({field}:{cid}) 内容="{comment}"')
    else:
        # 未匹配到注册用户 → 不做处理，等待管理员人工审核
        print(f'[GroupRequest] 未匹配注册用户，跳过: QQ={user_id} 群={group_id} 内容="{comment}"')


async def _find_identity_async(text):
    """异步包装：pymysql 是同步库，丢到线程池执行避免阻塞事件循环。"""
    import asyncio
    return await asyncio.to_thread(_find_identity, text)
