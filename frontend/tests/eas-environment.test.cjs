const assert = require("node:assert/strict")
const test = require("node:test")

const { build } = require("../eas.json")
const appConfig = require("../app.json").expo
const { dependencies } = require("../package.json")

test("internal device builds use production variables with direct-install signing", () => {
    assert.equal(build.internal.environment, "production")
    assert.equal(build.internal.environment, build.production.environment)
    assert.equal(build.internal.distribution, "internal")
    assert.equal(build.internal.channel, build.production.channel)
    assert.equal(build.internal.channel, undefined)
    assert.notEqual(build.internal.developmentClient, true)
})

test("release profiles use the embedded app without an OTA update channel", () => {
    assert.equal(dependencies["expo-updates"], undefined)
    assert.equal(appConfig.updates.enabled, false)
    assert.equal(appConfig.updates.url, undefined)
    assert.equal(appConfig.runtimeVersion, undefined)
    assert.equal(appConfig.ios.runtimeVersion, undefined)
    for (const name of ["testing", "testflight", "production"]) {
        assert.equal(build[name].channel, undefined)
        assert.notEqual(build[name].developmentClient, true)
    }
})
