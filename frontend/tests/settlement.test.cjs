/* global __dirname */
const test = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const moduleExports = require("./load-ts.cjs")("utils/settlement.ts")

test("balance keeps debt, kopecks and unknown separate from zero", () => {
    assert.match(moduleExports.formatSettlementMoney("-100000.25"), /-100\s000,25/)
    assert.match(moduleExports.formatSettlementMoney("0"), /0,00/)
    for (const value of [null, undefined, "", "NaN", "oops"]) {
        assert.equal(moduleExports.formatSettlementMoney(value), "—")
    }
})

test("zero program and unknown never default to accumulation", () => {
    assert.equal(moduleExports.settlementProgramKey(0), "profile.settlement.programNone")
    assert.equal(moduleExports.settlementProgramKey(null), "profile.settlement.programUnknown")
    assert.equal(moduleExports.settlementProgramKey(1), "profile.settlement.programBonus")
    assert.equal(moduleExports.settlementProgramKey(2), "profile.settlement.programReferral")
})

test("discount display uses the read-only account source", () => {
    const screen = fs.readFileSync(path.join(__dirname, "../screens/profile/profile-discounts-screen.tsx"), "utf8")
    assert.ok(screen.includes("getMySettlement"))
    assert.ok(!screen.includes("getMyReferralProfile"))
    assert.ok(!screen.includes("bonus_rubles"))
    assert.ok(screen.includes("key={user.id}"))
})
