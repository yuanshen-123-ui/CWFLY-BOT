"""航路查询服务 - 直接调用 CWFLY 官网航路 API。

推荐高度按 RVSM 规则计算：国内（中国大陆）用国内 RVSM，国外用国际 RVSM。
"""
import math
import re

from . import http

CFY_API = 'https://www.ccflysim.cn:8443/api'

# 常用机场坐标（用于计算航向/距离，缺失时跳过 RVSM 推荐）
AIRPORT_COORDS = {
    'ZSSS': {'lat': 31.1979, 'lon': 121.3363}, 'ZSPD': {'lat': 31.1434, 'lon': 121.8053},
    'ZBAA': {'lat': 40.0799, 'lon': 116.6031}, 'ZBAD': {'lat': 39.5098, 'lon': 116.4105},
    'ZGGG': {'lat': 23.3925, 'lon': 113.2988}, 'ZGSZ': {'lat': 22.6394, 'lon': 113.8142},
    'ZGHA': {'lat': 28.1892, 'lon': 113.2200}, 'ZGNN': {'lat': 22.6083, 'lon': 108.1725},
    'ZUCK': {'lat': 29.7192, 'lon': 106.6417}, 'ZUUU': {'lat': 30.5786, 'lon': 103.9469},
    'ZPPP': {'lat': 25.1019, 'lon': 102.9292}, 'ZPLJ': {'lat': 26.6792, 'lon': 100.2461},
    'ZSHC': {'lat': 30.2295, 'lon': 120.4344}, 'ZSNB': {'lat': 29.8267, 'lon': 121.4619},
    'ZSNJ': {'lat': 31.7420, 'lon': 118.8620}, 'ZSOF': {'lat': 31.9889, 'lon': 116.9789},
    'ZSAM': {'lat': 24.5439, 'lon': 118.1275}, 'ZSFZ': {'lat': 25.9333, 'lon': 119.6667},
    'ZGSD': {'lat': 22.0069, 'lon': 113.3747}, 'ZGHK': {'lat': 19.7933, 'lon': 110.4525},
    'ZJHK': {'lat': 19.9349, 'lon': 110.4590}, 'ZJSY': {'lat': 18.3029, 'lon': 109.4122},
    'ZWWW': {'lat': 43.9072, 'lon': 87.4742}, 'ZWSH': {'lat': 39.5433, 'lon': 76.0200},
    'ZLXY': {'lat': 34.4471, 'lon': 108.7516}, 'ZLLL': {'lat': 36.5152, 'lon': 103.6200},
    'ZYHB': {'lat': 45.6234, 'lon': 126.2503}, 'ZYCC': {'lat': 43.9959, 'lon': 125.6850},
    'ZYTL': {'lat': 38.9657, 'lon': 121.5386}, 'ZYTX': {'lat': 41.6401, 'lon': 123.4834},
    'ZBTJ': {'lat': 39.1244, 'lon': 117.3462}, 'ZBNY': {'lat': 40.0732, 'lon': 116.6416},
    'ZBHH': {'lat': 40.8500, 'lon': 111.8233}, 'ZBDT': {'lat': 40.0603, 'lon': 113.4823},
    'ZHHH': {'lat': 30.7838, 'lon': 114.2081},
    'ZUGY': {'lat': 26.5383, 'lon': 106.8014}, 'ZUKJ': {'lat': 26.3222, 'lon': 109.4450},
    'ZPKM': {'lat': 25.2167, 'lon': 102.7417}, 'ZPDQ': {'lat': 27.7936, 'lon': 99.6772},
    'ZWYN': {'lat': 39.2333, 'lon': 75.2333}, 'ZWAK': {'lat': 41.2633, 'lon': 80.2572},
    'ZSQD': {'lat': 36.2661, 'lon': 120.3744}, 'ZSJN': {'lat': 36.8572, 'lon': 117.2161},
    'RCTP': {'lat': 25.0764, 'lon': 121.2239}, 'RCSS': {'lat': 25.0697, 'lon': 121.5525},
    'VHHH': {'lat': 22.3080, 'lon': 113.9185}, 'VMMC': {'lat': 22.1495, 'lon': 113.5914},
    'RJTT': {'lat': 35.5494, 'lon': 139.7798}, 'RJBB': {'lat': 34.4320, 'lon': 135.2304},
    'RKSI': {'lat': 37.4602, 'lon': 126.4407}, 'RKSS': {'lat': 37.5583, 'lon': 126.7906},
}

# 中国大陆机场 ICAO 第二个字母
CN_SECOND = set('BGHJLP SUYVWQ')


def is_domestic_icao(icao):
    """是否中国大陆机场（用于判断国内/国外 RVSM）。"""
    code = str(icao or '').upper()
    return len(code) >= 2 and code[0] == 'Z' and code[1] in CN_SECOND


def get_initial_bearing(lat1, lon1, lat2, lon2):
    """大圆起始方位角（度，0-359，000-179 为东向）。"""
    rad = math.pi / 180
    phi1 = lat1 * rad
    phi2 = lat2 * rad
    dlam = (lon2 - lon1) * rad
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.atan2(y, x) * 180 / math.pi + 360) % 360


def great_circle_nm(lat1, lon1, lat2, lon2):
    """大圆距离（海里）。"""
    r = 3440.065
    rad = math.pi / 180
    phi1 = lat1 * rad
    phi2 = lat2 * rad
    dphi = (lat2 - lat1) * rad
    dlam = (lon2 - lon1) * rad
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def round_to_rvsm(alt_ft, eastward, domestic):
    """按 RVSM 规则将基准高度取整到合法高度层。"""
    odd = [290, 310, 330, 350, 370, 390, 410]          # 东向层
    even_dom = [300, 320, 340, 360, 380, 400]          # 国内西向层
    even_intl = [280, 300, 320, 340, 360, 380, 400]    # 国际西向层
    table = odd if eastward else (even_dom if domestic else even_intl)
    fl = round(alt_ft / 100)
    best = table[0]
    best_diff = abs(table[0] - fl)
    for t in table:
        d = abs(t - fl)
        if d < best_diff:
            best, best_diff = t, d
    return best


def fl_to_meters_cn(fl):
    """中国 RVSM 高度层：FL → 米制（China RVSM FLAS）。"""
    mapping = {
        290: 8900, 310: 9500, 330: 10100, 350: 10700, 370: 11300, 390: 11900, 410: 12500,
        300: 9200, 320: 9800, 340: 10400, 360: 11000, 380: 11600, 400: 12200,
    }
    return mapping.get(fl, '')


def estimate_base_alt(nm):
    """无官网高度时按距离估算基准高度。"""
    if nm < 400:
        return 29000
    if nm < 800:
        return 33000
    if nm < 1500:
        return 35000
    return 37000


async def query_route(dep, arr):
    """查询航路（官网 API，返回 SimBrief 格式）。"""
    try:
        url = f'{CFY_API}/route?dep={dep}&arr={arr}'
        resp = await http.http_get(
            url, timeout=15,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; CWFLY/1.0)'})
        if resp.status_code != 200:
            return '航路服务暂时不可用。'
        json_data = resp.json()
        if json_data.get('success') is False:
            return '航路服务暂时不可用。'

        lines = [f'航路查询 {dep} → {arr}']

        # 官网 API 返回 SimBrief 文本格式，提取 Route= 与 Altitude=
        route_str = json_data.get('route') or ''
        altitude = None
        route_line = None
        m = re.search(r'Altitude=(\S+)', route_str)
        if m:
            altitude = m.group(1)
        m = re.search(r'Route=\s*([^\r\n]+)', route_str)
        if m:
            route_line = m.group(1)
        if route_line:
            r = route_line.strip()
            lines.append(f'航路：{r[:500] + "…" if len(r) > 500 else r}')

        # 计算推荐高度（按国内/国外 RVSM 规则）
        dep_pos = AIRPORT_COORDS.get(dep.upper())
        arr_pos = AIRPORT_COORDS.get(arr.upper())
        domestic = is_domestic_icao(dep) and is_domestic_icao(arr)
        eastward = None
        nm = None
        if dep_pos and arr_pos:
            bearing = get_initial_bearing(dep_pos['lat'], dep_pos['lon'],
                                          arr_pos['lat'], arr_pos['lon'])
            eastward = bearing < 180
            nm = great_circle_nm(dep_pos['lat'], dep_pos['lon'],
                                 arr_pos['lat'], arr_pos['lon'])

        if eastward is not None:
            base = float(altitude) if altitude else estimate_base_alt(nm or 0)
            if base:
                fl = round_to_rvsm(base, eastward, domestic)
                direction = '东向' if eastward else '西向'
                if domestic:
                    # 中国 RVSM：米制显示（China RVSM FLAS）
                    meters = fl_to_meters_cn(fl)
                    label = f'{meters}米' if meters else f'FL{fl}'
                    lines.append(f'推荐高度：{label}（国内RVSM·{direction}）')
                else:
                    # 国际 RVSM：英制 FL 显示
                    lines.append(f'推荐高度：FL{fl}（国际RVSM·{direction}）')
        elif altitude:
            lines.append(f'推荐高度：{altitude}')

        return '\n'.join(lines)
    except Exception:
        return '航路服务暂时不可用。'
