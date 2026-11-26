const assert = require("node:assert/strict")
const { execFileSync } = require("node:child_process")
const path = require("node:path")
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

test("local and iOS builds retain their existing updates configuration", () => {
    assert.equal(appConfig.updates.enabled, false)
    assert.equal(appConfig.updates.url, undefined)
    assert.equal(appConfig.runtimeVersion, undefined)
    assert.equal(appConfig.ios.runtimeVersion, undefined)
    for (const name of ["testing", "testflight", "production"]) {
        assert.equal(build[name].channel, undefined)
        assert.notEqual(build[name].developmentClient, true)
    }
})

test("the current Android store build and its OTA command share a dedicated runtime", t => {
    const previous = process.env.ELIXIR_ANDROID_STORE
    t.after(() => {
        if (previous === undefined) delete process.env.ELIXIR_ANDROID_STORE
        else process.env.ELIXIR_ANDROID_STORE = previous
    })
    const profile = build.production.android
    assert.equal(profile.channel, "production")
    assert.equal(profile.buildType, "app-bundle")
    assert.equal(profile.env.ELIXIR_ANDROID_STORE, "1")
    assert.equal(build.production.autoIncrement, true)
    process.env.ELIXIR_ANDROID_STORE = profile.env.ELIXIR_ANDROID_STORE
    const { expo } = require("../app.config.js")()
    assert.equal(expo.version, "0.1.2")
    assert.equal(expo.android.runtimeVersion, expo.version)
    assert.equal(expo.android.package, "com.elixirpeptide.elixirpeptide")
    assert.equal(expo.updates.enabled, true)
    assert.equal(expo.updates.url, `https://u.expo.dev/${expo.extra.eas.projectId}`)
    const command = require("../package.json").scripts["ota:android:store"]
    assert.match(command, /ELIXIR_ANDROID_STORE=1 /)
    assert.match(command, /--platform android --channel production --environment production/)
    assert.doesNotMatch(command, /ELIXIR_PLAY_OTA/)
})

test("the store prebuild writes the configured MapKit key into the Android manifest", () => {
    const projectRoot = path.dirname(require.resolve("../package.json"))
    const config = execFileSync(process.execPath, ["node_modules/expo/bin/cli", "config", "--type", "introspect", "--json"], {
        cwd: projectRoot,
        env: { ...process.env, ELIXIR_ANDROID_STORE: "1", ELIXIR_PLAY_OTA: "0", EXPO_NO_DOTENV: "0", YANDEX_MAPKIT_API_KEY: "test-map-key" },
        encoding: "utf8",
    })
    const manifest = JSON.parse(config)._internal.modResults.android.manifest.manifest
    const entry = manifest.application[0]["meta-data"].find(item => item.$["android:name"] === "YANDEX_MAPKIT_API_KEY")
    assert.equal(entry?.$["android:value"], "test-map-key")
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
