/**
 * 航路查询服务 - 直接调用 CWFLY 官网航路 API
 * 推荐高度按 RVSM 规则计算：国内（中国大陆）用国内 RVSM，国外用国际 RVSM
 */

const CFY_API = 'https://www.ccflysim.cn:8443/api'

// 常用机场坐标（用于计算航向/距离，缺失时跳过 RVSM 推荐）
const AIRPORT_COORDS = {
  ZSSS: { lat: 31.1979, lon: 121.3363 }, ZSPD: { lat: 31.1434, lon: 121.8053 },
  ZBAA: { lat: 40.0799, lon: 116.6031 }, ZBAD: { lat: 39.5098, lon: 116.4105 },
  ZGGG: { lat: 23.3925, lon: 113.2988 }, ZGSZ: { lat: 22.6394, lon: 113.8142 },
  ZGHA: { lat: 28.1892, lon: 113.2200 }, ZGNN: { lat: 22.6083, lon: 108.1725 },
  ZUCK: { lat: 29.7192, lon: 106.6417 }, ZUUU: { lat: 30.5786, lon: 103.9469 },
  ZPPP: { lat: 25.1019, lon: 102.9292 }, ZPLJ: { lat: 26.6792, lon: 100.2461 },
  ZSHC: { lat: 30.2295, lon: 120.4344 }, ZSNB: { lat: 29.8267, lon: 121.4619 },
  ZSNJ: { lat: 31.7420, lon: 118.8620 }, ZSOF: { lat: 31.9889, lon: 116.9789 },
  ZSAM: { lat: 24.5439, lon: 118.1275 }, ZSFZ: { lat: 25.9333, lon: 119.6667 },
  ZGSD: { lat: 22.0069, lon: 113.3747 }, ZGHK: { lat: 19.7933, lon: 110.4525 },
  ZJHK: { lat: 19.9349, lon: 110.4590 }, ZJSY: { lat: 18.3029, lon: 109.4122 },
  ZWWW: { lat: 43.9072, lon: 87.4742 }, ZWSH: { lat: 39.5433, lon: 76.0200 },
  ZLXY: { lat: 34.4471, lon: 108.7516 }, ZLLL: { lat: 36.5152, lon: 103.6200 },
  ZYHB: { lat: 45.6234, lon: 126.2503 }, ZYCC: { lat: 43.9959, lon: 125.6850 },
  ZYTL: { lat: 38.9657, lon: 121.5386 }, ZYTX: { lat: 41.6401, lon: 123.4834 },
  ZBTJ: { lat: 39.1244, lon: 117.3462 }, ZBNY: { lat: 40.0732, lon: 116.6416 },
  ZBHH: { lat: 40.8500, lon: 111.8233 }, ZBDT: { lat: 40.0603, lon: 113.4823 },
  ZHHH: { lat: 30.7838, lon: 114.2081 },
  ZUGY: { lat: 26.5383, lon: 106.8014 }, ZUKJ: { lat: 26.3222, lon: 109.4450 },
  ZPKM: { lat: 25.2167, lon: 102.7417 }, ZPDQ: { lat: 27.7936, lon: 99.6772 },
  ZWYN: { lat: 39.2333, lon: 75.2333 }, ZWAK: { lat: 41.2633, lon: 80.2572 },
  ZSQD: { lat: 36.2661, lon: 120.3744 }, ZSJN: { lat: 36.8572, lon: 117.2161 },
  RCTP: { lat: 25.0764, lon: 121.2239 }, RCSS: { lat: 25.0697, lon: 121.5525 },
  VHHH: { lat: 22.3080, lon: 113.9185 }, VMMC: { lat: 22.1495, lon: 113.5914 },
  RJTT: { lat: 35.5494, lon: 139.7798 }, RJBB: { lat: 34.4320, lon: 135.2304 },
  RKSI: { lat: 37.4602, lon: 126.4407 }, RKSS: { lat: 37.5583, lon: 126.7906 },
}

// 中国大陆机场 ICAO 第二个字母
const CN_SECOND = new Set(['B', 'G', 'H', 'J', 'L', 'P', 'S', 'U', 'Y', 'V', 'W', 'Q'])

/** 是否中国大陆机场（用于判断国内/国外 RVSM） */
function isDomesticIcao(icao) {
  const code = String(icao || '').toUpperCase()
  return code.length >= 2 && code[0] === 'Z' && CN_SECOND.has(code[1])
}

/** 大圆起始方位角（度，0-359，000-179 为东向） */
function getInitialBearing(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180
  const φ1 = lat1 * rad
  const φ2 = lat2 * rad
  const Δλ = (lon2 - lon1) * rad
  const y = Math.sin(Δλ) * Math.cos(φ2)
  const x = Math.cos(φ1) * Math.sin(φ2) - Math.sin(φ1) * Math.cos(φ2) * Math.cos(Δλ)
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360
}

/** 大圆距离（海里） */
function greatCircleNm(lat1, lon1, lat2, lon2) {
  const R = 3440.065
  const rad = Math.PI / 180
  const φ1 = lat1 * rad
  const φ2 = lat2 * rad
  const Δφ = (lat2 - lat1) * rad
  const Δλ = (lon2 - lon1) * rad
  const a = Math.sin(Δφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(Δλ / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

/** 按 RVSM 规则将基准高度取整到合法高度层 */
function roundToRVSM(altFt, eastward, domestic) {
  const odd = [290, 310, 330, 350, 370, 390, 410]          // 东向层
  const evenDom = [300, 320, 340, 360, 380, 400]           // 国内西向层
  const evenIntl = [280, 300, 320, 340, 360, 380, 400]     // 国际西向层
  const table = eastward ? odd : (domestic ? evenDom : evenIntl)
  const fl = Math.round(altFt / 100)
  let best = table[0]
  let bestDiff = Math.abs(table[0] - fl)
  for (const t of table) {
    const d = Math.abs(t - fl)
    if (d < bestDiff) { best = t; bestDiff = d }
  }
  return best
}

/** 中国 RVSM 高度层：FL → 米制（China RVSM FLAS） */
function flToMetersCn(fl) {
  const map = {
    290: 8900, 310: 9500, 330: 10100, 350: 10700, 370: 11300, 390: 11900, 410: 12500,
    300: 9200, 320: 9800, 340: 10400, 360: 11000, 380: 11600, 400: 12200,
  }
  return map[fl] || ''
}

/** 无官网高度时按距离估算基准高度 */
function estimateBaseAlt(nm) {
  if (nm < 400) return 29000
  if (nm < 800) return 33000
  if (nm < 1500) return 35000
  return 37000
}

/**
 * 查询航路（官网 API，返回 SimBrief 格式）
 * @param {string} dep - 起飞机场 ICAO
 * @param {string} arr - 降落机场 ICAO
 * @returns {Promise<string>}
 */
export async function queryRoute(dep, arr) {
  try {
    const url = `${CFY_API}/route?dep=${dep}&arr=${arr}`
    const response = await fetch(url, {
      signal: AbortSignal.timeout(15_000),
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; CWFLY/1.0)' }
    })
    if (!response.ok) return '航路服务暂时不可用。'

    const json = await response.json()
    if (json.success === false) return '航路服务暂时不可用。'

    const lines = [`航路查询 ${dep} → ${arr}`]

    // 官网 API 返回 SimBrief 文本格式，提取 Route= 与 Altitude=
    const routeStr = json.route || ''
    const altitude = (routeStr.match(/Altitude=(\S+)/) || [])[1]
    const routeLine = (routeStr.match(/Route=\s*([^\r\n]+)/) || [])[1]
    if (routeLine) {
      const r = routeLine.trim()
      lines.push(`航路：${r.length > 500 ? r.slice(0, 500) + '…' : r}`)
    }

    // 计算推荐高度（按国内/国外 RVSM 规则）
    const depPos = AIRPORT_COORDS[dep.toUpperCase()]
    const arrPos = AIRPORT_COORDS[arr.toUpperCase()]
    const domestic = isDomesticIcao(dep) && isDomesticIcao(arr)
    let eastward = null
    let nm = null
    if (depPos && arrPos) {
      const bearing = getInitialBearing(depPos.lat, depPos.lon, arrPos.lat, arrPos.lon)
      eastward = bearing < 180
      nm = greatCircleNm(depPos.lat, depPos.lon, arrPos.lat, arrPos.lon)
    }

    if (eastward !== null) {
      const base = altitude ? Number(altitude) : estimateBaseAlt(nm || 0)
      if (base) {
        const fl = roundToRVSM(base, eastward, domestic)
        const dir = eastward ? '东向' : '西向'
        if (domestic) {
          // 中国 RVSM：米制显示（China RVSM FLAS）
          const meters = flToMetersCn(fl)
          lines.push(`推荐高度：${meters ? `${meters}米` : `FL${fl}`}（国内RVSM·${dir}）`)
        } else {
          // 国际 RVSM：英制 FL 显示
          lines.push(`推荐高度：FL${fl}（国际RVSM·${dir}）`)
        }
      }
    } else if (altitude) {
      lines.push(`推荐高度：${altitude}`)
    }

    if (lines.length === 1) {
      return `无法获取 ${dep}→${arr} 的航路信息。`
    }

    return lines.join('\n')
  } catch (err) {
    if (err.name === 'AbortError') return '航路查询超时，请稍后重试。'
    return '航路服务暂时不可用。'
  }
}
