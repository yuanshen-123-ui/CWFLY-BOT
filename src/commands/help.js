/**
 * /帮助 - 命令帮助列表
 *
 * 布局：每行只显示一个命令（中文优先；metar/taf 保留英文），
 *       命令与注释用少量空格分隔，不强制对齐。
 */

/** 分组：标题 + 命令条目 [命令(含参数), 说明] */
const SECTIONS = [
  {
    title: '📡 在线状态',
    items: [
      ['/在线状态', '查看 FSD 连接概况'],
    ],
  },
  {
    title: '🧭 查询',
    items: [
      ['/机组查询', '查询在线机组（含飞行计划）'],
      ['/管制查询', '查询在线管制'],
    ],
  },
  {
    title: '🌤️ 航空气象',
    items: [
      ['/metar <ICAO>', '查询 METAR'],
      ['/taf <ICAO1,ICAO2>', '查询 TAF（最多 5 个）'],
    ],
  },
  {
    title: '🛫 飞行规划',
    items: [
      ['/航路 <DEP> <ARR>', '查询航路'],
      ['/机场查询 <ICAO>', '查询机场信息'],
    ],
  },
  {
    title: '🧠 AI 助手',
    items: [
      ['/聊天 <内容>', '专业飞行问答'],
    ],
  },
  {
    title: '🎉 活动',
    items: [
      ['/活动', '查看近期连飞活动'],
    ],
  },
  {
    title: '⚙️ 其他',
    items: [
      ['/呼叫管制', '呼叫在线管制员'],
      ['/呼叫2325', '呼叫管制员 2325'],
      ['/帮助', '显示此帮助'],
    ],
  },
]

export async function handleHelp(ws, event, args) {
  const { sendGroupMessage, sendPrivateMessage } = await import('../utils/onebot.js')
  const send = (msg) => {
    if (event.message_type === 'group') sendGroupMessage(ws, event.group_id, msg)
    else sendPrivateMessage(ws, event.user_id, msg)
  }

  const lines = [
    '🚀 CWFLY 飞控机器人',
    '━━━━━━━━━━━━━━━━━━━━',
  ]

  for (const section of SECTIONS) {
    lines.push('')
    lines.push(section.title)
    for (const [cmd, desc] of section.items) {
      lines.push(`  ${cmd}  ${desc}`)
    }
  }

  send(lines.join('\n'))
}
