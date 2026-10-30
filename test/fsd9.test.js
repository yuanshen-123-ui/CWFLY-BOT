import test from 'node:test'
import assert from 'node:assert/strict'
import { parseClientAddLine } from '../src/services/fsd9.js'

test('parseClientAddLine handles ATC and PILOT formats from CWFLY FSD', () => {
  const atc = parseClientAddLine('#AAZBAA_TWR::Test ATC:123456:1:9', 2)
  assert.equal(atc?.callsign, 'ZBAA_TWR')
  assert.equal(atc?.cid, '123456')
  assert.equal(atc?.rating, 9)
  assert.equal(atc?.type, 'ATC')

  const pilot = parseClientAddLine('#APCSN1234:2:654321:1:9:0:Test Pilot', 1)
  assert.equal(pilot?.callsign, 'CSN1234')
  assert.equal(pilot?.cid, '654321')
  assert.equal(pilot?.rating, 9)
  assert.equal(pilot?.type, 'PILOT')
})
