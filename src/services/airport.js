/**
 * 机场查询服务
 * 使用 OurAirports 官方数据，从 CSV 加载到内存 Map
 */

import { readFileSync, existsSync, mkdirSync } from 'fs'
import { join, dirname } from 'path'
import { parse } from 'csv-parse/sync'

const CACHE_FILE = process.env.AIRPORT_CACHE_FILE || join(process.cwd(), 'data', 'airports.csv')
const OUR_AIRPORTS_URL =
  'https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv'

/** @type {Map<string, object>} */
let airportMap = null
let lastFetch = 0

/**
 * 确保缓存目录存在
 */
function ensureCacheDir() {
  const dir = dirname(CACHE_FILE)
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
}

/**
 * 下载机场数据
 */
async function downloadAirportData() {
  ensureCacheDir()
  const response = await fetch(OUR_AIRPORTS_URL, {
    signal: AbortSignal.timeout(30_000)
  })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  const text = await response.text()
  const { writeFileSync } = await import('fs')
  writeFileSync(CACHE_FILE, text, 'utf-8')
  lastFetch = Date.now()
  return text
}

/**
 * 读取机场数据，如需则下载更新
 */
async function loadAirports() {
  if (airportMap) {
    // 每 24 小时检查更新
    if (Date.now() - lastFetch < 86_400_000) return
  }

  let csvText
  try {
    if (existsSync(CACHE_FILE)) {
      const { readFileSync } = await import('fs')
      csvText = readFileSync(CACHE_FILE, 'utf-8')
      lastFetch = Date.now()
      // 检查文件是否过期（超过 24 小时）
      const stat = await import('fs').then(m => m.statSync(CACHE_FILE))
      if (Date.now() - stat.mtimeMs > 86_400_000) {
        // 尝试后台更新
        downloadAirportData().catch(() => {})
      }
    } else {
      csvText = await downloadAirportData()
    }
  } catch {
    // 如果无法下载且无缓存，使用空数据
    airportMap = new Map()
    return
  }

  try {
    const records = parse(csvText, {
      columns: true,
      skip_empty_lines: true,
      relax_column_count: true
    })

    const map = new Map()
    for (const row of records) {
      const ident = row.ident?.toUpperCase()
      if (ident && row.type && row.type !== 'closed') {
        map.set(ident, row)
      }
    }
    airportMap = map
  } catch {
    if (!airportMap) airportMap = new Map()
  }
}

/**
 * 查询机场信息
 * @param {string} icao - 4 位 ICAO 代码
 * @returns {Promise<string>}
 */
export async function queryAirport(icao) {
  await loadAirports()

  const code = icao.toUpperCase()
  const airport = airportMap?.get(code)

  if (!airport) return `未找到机场「${code}」`

  const typeMap = {
    large_airport: '大型机场',
    medium_airport: '中型机场',
    small_airport: '小型机场',
    heliport: '直升机场',
    seaplane_base: '水上飞机基地',
    closed: '已关闭'
  }

  const lines = [`${code} ${airport.name || '未知'}国际机场`]
  lines.push(`类型：${typeMap[airport.type] || airport.type || '未知'}`)
  if (airport.municipality) lines.push(`城市：${airport.municipality}`)
  if (airport.iso_country) {
    const countryNames = {
      CN: '中国', US: '美国', GB: '英国', JP: '日本',
      KR: '韩国', DE: '德国', FR: '法国', AU: '澳大利亚',
      CA: '加拿大', SG: '新加坡', RU: '俄罗斯', HK: '中国香港',
      MO: '中国澳门', TW: '中国台湾'
    }
    lines.push(`国家：${countryNames[airport.iso_country] || airport.iso_country}`)
  }
  if (airport.latitude_deg && airport.longitude_deg) {
    lines.push(`坐标：${Number(airport.latitude_deg).toFixed(4)}, ${Number(airport.longitude_deg).toFixed(4)}`)
  }
  if (airport.elevation_ft) lines.push(`标高：${airport.elevation_ft} ft`)
  if (airport.home_link) lines.push(`网址：${airport.home_link}`)

  return lines.join('\n')
}
