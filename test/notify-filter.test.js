// 免播报名单单测：node test/notify-filter.test.js
import assert from 'node:assert'

process.env.NOTIFY_SKIP_CIDS = '5966,0000'
process.env.NOTIFY_SKIP_CALLSIGNS = 'ZBAA_APP'

const { isNotifySkipped } = await import('../src/utils/notifyFilter.js')

let pass = 0
const cases = [
  ['命中 CID', { cid: '5966', callsign: 'ZSHA_CTR' }, true],
  ['命中 CID（数字型）', { cid: 5966, callsign: 'ZSSS_TWR' }, true],
  ['命中呼号', { cid: '9999', callsign: 'zbaa_app' }, true],
  ['不在名单', { cid: '1234', callsign: 'ZBAA_TWR' }, false],
  ['空对象', {}, false],
  ['null', null, false]
]
for (const [name, ctrl, expected] of cases) {
  const got = isNotifySkipped(ctrl)
  assert.strictEqual(got, expected, `${name}: expected ${expected}, got ${got}`)
  console.log(`  ✔ ${name}`)
  pass++
}
console.log(`\n通过 ${pass} 项，失败 0 项`)
