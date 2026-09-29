const test = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const ts = require("typescript")
const path = require("node:path")
const source = fs.readFileSync(path.join(__dirname, "../utils/settlement.ts"), "utf8")
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText
const moduleExports = {}
new Function("exports", compiled)(moduleExports)

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

test("account display does not call the legacy mutating referral summary", () => {
    const screen = fs.readFileSync(path.join(__dirname, "../screens/profile/profile-settlement-screen.tsx"), "utf8")
    assert.ok(screen.includes("getMySettlement"))
    assert.ok(!screen.includes("getMyReferralProfile"))
    assert.ok(!screen.includes("bonus_rubles"))
    assert.ok(screen.includes("key={user.id}"))
})

test("new account view is opt-in without removing the legacy view", () => {
    const screen = fs.readFileSync(path.join(__dirname, "../screens/profile/profile-discounts-screen.tsx"), "utf8")
    assert.ok(screen.includes('process.env.EXPO_PUBLIC_MS_ACCOUNT_VIEW_ENABLED === "true"'))
    assert.ok(screen.includes("<LegacyProfileDiscountsScreen />"))
    assert.ok(screen.includes("attachMyReferrerCode"))
})
