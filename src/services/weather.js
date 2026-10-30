/**
 * 航空气象服务 - 复用现有 CWFLY 后端 API
 */

import { normalizeIcao } from '../utils/validator.js'

const CWFLY_API_URL = process.env.CWFLY_API_URL || 'http://127.0.0.1:3000/api'

/**
 * 获取某个机场的天气数据
 * @param {string} icao - 4 位 ICAO 代码
 * @returns {Promise<{metar: string, taf: string}|null>}
 */
export async function getWeather(icao) {
  const url = `${CWFLY_API_URL}/weather?icao=${icao}`
  const response = await fetch(url, {
    signal: AbortSignal.timeout(8000)
  })
  if (!response.ok) return null
  const json = await response.json()
  if (!json.success) return null
  return json.data || null
}

/**
 * 格式化单个机场的 METAR
 * @param {string} icao
 * @returns {Promise<string>}
 */
export async function formatMetar(icao) {
  try {
    const data = await getWeather(icao)
    if (!data) return `无法获取 ${icao} 的气象数据。`
    const metar = data.metar || '无 METAR 数据'
    return `${icao} METAR\n${metar}`
  } catch {
    return `${icao} 气象服务暂时不可用。`
  }
}

/**
 * 格式化单个或多个机场的 TAF
 * @param {string} icaoInput - ICAO 列表，逗号分隔
 * @returns {Promise<string>}
 */
export async function formatTaf(icaoInput) {
  // 服务层兜底校验：只查询合法的 4 位字母 ICAO 代码
  const icaos = icaoInput.split(/[,，\s]+/)
    .map(normalizeIcao)
    .filter(Boolean)
    .slice(0, 5)
  if (icaos.length === 0) return '请指定有效的 ICAO 代码（4 位字母）。'

  const results = await Promise.allSettled(
    icaos.map(async (icao) => {
      const data = await getWeather(icao)
      if (!data) return `${icao}：无法获取数据`
      const taf = data.taf || `无 TAF 数据`
      return `${icao} TAF\n${taf}`
    })
  )

  return results
    .map(r => r.status === 'fulfilled' ? r.value : '查询失败')
    .join('\n\n')
}
