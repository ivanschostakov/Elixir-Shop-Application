const assert = require("node:assert/strict")
const test = require("node:test")

const { build } = require("../eas.json")

test("internal device builds use production variables with direct-install signing", () => {
    assert.equal(build.internal.environment, "production")
    assert.equal(build.internal.environment, build.production.environment)
    assert.equal(build.internal.distribution, "internal")
    assert.equal(build.internal.channel, build.production.channel)
    assert.equal(build.internal.channel, "production")
    assert.notEqual(build.internal.developmentClient, true)
})
