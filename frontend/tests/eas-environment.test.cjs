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

test("regular build profiles still launch their embedded app", () => {
    assert.equal(appConfig.updates.enabled, false)
    assert.equal(appConfig.updates.url, undefined)
    assert.equal(appConfig.runtimeVersion, undefined)
    assert.equal(appConfig.ios.runtimeVersion, undefined)
    for (const name of ["testing", "testflight", "production"]) {
        assert.equal(build[name].channel, undefined)
        assert.notEqual(build[name].developmentClient, true)
    }
})

test("the Play OTA command uses build 6's runtime, project, platform and channel", t => {
    const previous = process.env.ELIXIR_PLAY_OTA
    t.after(() => {
        if (previous === undefined) delete process.env.ELIXIR_PLAY_OTA
        else process.env.ELIXIR_PLAY_OTA = previous
    })
    process.env.ELIXIR_PLAY_OTA = "1"
    const { expo } = require("../app.config.js")()
    assert.equal(dependencies["expo-updates"], "29.0.18")
    assert.equal(expo.updates.enabled, true)
    assert.equal(expo.updates.url, "https://u.expo.dev/32dfb6b0-55a1-4dcc-aeab-91b3633cfed6")
    assert.equal(expo.android.runtimeVersion, "0.1.1")
    assert.equal(expo.ios.runtimeVersion ?? expo.runtimeVersion, undefined)
    assert.match(require("../package.json").scripts["ota:android"], /--platform android --channel production --environment production/)
})
