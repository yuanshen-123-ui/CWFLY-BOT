"""异步 HTTP 封装。

使用 requests 走线程池，避免阻塞 asyncio 事件循环。
"""
import asyncio

import requests


async def http_get(url, *, timeout=10, headers=None):
    return await asyncio.to_thread(_get, url, timeout, headers)


def _get(url, timeout, headers):
    return requests.get(url, timeout=timeout, headers=headers or {})


async def http_post(url, *, timeout=10, headers=None, json=None):
    return await asyncio.to_thread(_post, url, timeout, headers, json)


def _post(url, timeout, headers, json_body):
    return requests.post(url, timeout=timeout, headers=headers or {}, json=json_body)
