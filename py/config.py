"""配置加载：读取 .env 文件并暴露常用配置。

与 Node 版（dotenv/config）行为一致：从 bot 根目录 .env 加载环境变量，
未设置时使用默认值。
"""
import os
from pathlib import Path

_BASE = Path(__file__).resolve().parent


def _load_dotenv(*paths):
    for p in paths:
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding='utf-8')
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ.setdefault(key, value)


# 优先读取脚本同级 .env，其次读取父目录（bot 根）的 .env
_load_dotenv(_BASE / '.env', _BASE.parent / '.env')


def env(key, default=''):
    return os.environ.get(key, default)


def env_int(key, default=0):
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def env_bool(key, default=False):
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ('1', 'true', 'yes', 'on')


# ---- OneBot 反向 WebSocket ----
WS_HOST = env('BOT_WS_HOST', '127.0.0.1')
WS_PORT = env_int('BOT_WS_PORT', 6700)
ACCESS_TOKEN = env('ONEBOT_ACCESS_TOKEN', '')
BOT_SELF_ID = env('BOT_SELF_ID', '')

# ---- 上游 API ----
FSD_API_URL = env('FSD_API_URL', 'http://127.0.0.1:8080/api')
CWFLY_API_URL = env('CWFLY_API_URL', 'http://127.0.0.1:3000/api')
API_BASE = env('API_BASE', 'http://localhost:3000/api')

# ---- FSD9 协议直连 ----
FSD_HOST = env('FSD_HOST', '127.0.0.1')
FSD_PORT = env_int('FSD_PORT', 6809)
FSD_BOT_CALLSIGN = env('FSD_BOT_CALLSIGN', 'CW-BOT')
FSD_BOT_CID = env('FSD_BOT_CID', '0000')
FSD_BOT_PASSWORD = env('FSD_BOT_PASSWORD', '')  # fail-closed：不再回落弱默认值

# ---- AI ----
AI_BASE_URL = env('AI_BASE_URL', 'https://ai.qingyu.ink/v1')
AI_API_KEY = env('AI_API_KEY', '')
AI_MODEL = env('AI_MODEL', 'deepseek-v4-flash-0731')
AI_MODELS = env('AI_MODELS', AI_MODEL)  # 多模型逗号分隔，按顺序切换

# ---- 群权限 ----
def allowed_group_ids():
    raw = env('ALLOWED_GROUP_IDS', '')
    return {x.strip() for x in raw.split(',') if x.strip()}


def control_group_id():
    return env('CONTROL_GROUP_ID', '')


def notify_group_id():
    return env('NOTIFY_GROUP_ID', env('CONTROL_GROUP_ID', ''))


def call_2325_qq():
    return env('CALL_2325_QQ', '3284715587')


def airport_cache_file():
    return env('AIRPORT_CACHE_FILE', str(_BASE / 'data' / 'airports.csv'))
