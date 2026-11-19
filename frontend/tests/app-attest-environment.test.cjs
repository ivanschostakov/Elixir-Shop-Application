const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

test("App Attest follows Xcode Debug/Release without an environment override", t => {
    const previous = process.env.APP_ATTEST_ENVIRONMENT
    process.env.APP_ATTEST_ENVIRONMENT = "development"
    t.after(() => {
        if (previous === undefined) delete process.env.APP_ATTEST_ENVIRONMENT
        else process.env.APP_ATTEST_ENVIRONMENT = previous
    })
    const configurations = {
        debug: { name: "Debug", buildSettings: {} },
        release: { name: "Release", buildSettings: {} },
    }
    let entitlements
    const plugin = loadTs("plugins/with-app-attest-environment.js", {
        "expo/config-plugins": {
            createRunOncePlugin: fn => fn,
            withEntitlementsPlist: (config, action) => {
                const result = action({ modResults: {} })
                entitlements = result.modResults
                return config
            },
            withXcodeProject: (config, action) => {
                action({ modResults: { pbxXCBuildConfigurationSection: () => configurations } })
                return config
            },
        },
    })
    plugin({})
    assert.equal(entitlements["com.apple.developer.devicecheck.appattest-environment"], "$(APP_ATTEST_ENVIRONMENT)")
    assert.equal(configurations.debug.buildSettings.APP_ATTEST_ENVIRONMENT, "development")
    assert.equal(configurations.release.buildSettings.APP_ATTEST_ENVIRONMENT, "production")
})
