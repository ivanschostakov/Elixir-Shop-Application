const test = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const deadlines = loadTs("services/api/request-deadline.ts")

const proof = { appIntegrityAction: "payments:create" }

function clientFor(responses) {
    let proofs = 0, requests = 0
    const native = { Platform: { OS: "android" } }
    const integrity = { AppIntegrityUnavailableError: class extends Error {},
        getAppIntegrityHeaders: async () => { proofs++; return {} },
        resetAppIntegrityState: async () => assert.fail("do not reset and replay a payment") }
    const api = loadTs("services/api/client.ts", {
        "react-native": native, "@/services/api/constants": { API_BASE_URL: "https://example.test" },
        "@/services/app-integrity": integrity,
        "@/services/auth/session": { getAuthTokens: () => ({ sessionId: "test" }) },
        "@/screens/chat/companion-timezones": { deviceCompanionTimezone: () => "UTC" },
        "@/services/api/request-deadline": { ...deadlines, fetchTextWithDeadline: async () => {
            const [status, detail] = responses[requests++]
            return { response: { status, ok: status === 200 }, text: JSON.stringify({ detail }) }
        } },
    })
    const alerts = [], opened = []
    const ui = loadTs("utils/errors.ts", {
        "react-native": { Alert: { alert: (...args) => alerts.push(args) }, Linking: { openURL: async url => opened.push(url) } },
        "@/services/api/client": api, "@/services/app-integrity": integrity, "@/i18n/translations": { translate: key => key },
    })
    return { api, ui, alerts, opened, count: () => ({ proofs, requests }) }
}

for (const [code, key] of [
    ["android_app_unrecognized", "playUpdate"], ["android_app_unevaluated", "playUnevaluated"],
    ["android_device_unverified", "playDevice"], ["android_signing_mismatch", "playSigning"],
]) {
    test(code + " is actionable without replaying checkout", async () => {
        const { api, ui, count, alerts, opened } = clientFor([[403, { code, message: "Verification failed" }]])
        await assert.rejects(api.apiPost("/payments/create", {}, proof), err => {
            assert.equal(ui.getErrorMessage(err), "auth.error." + key)
            ui.showBackendErrorAlert(err)
            return true
        })
        assert.deepEqual(count(), { proofs: 1, requests: 1 })
        assert.equal(alerts.length, 1)
        if (key === "playUpdate") {
            alerts[0][2][1].onPress()
            assert.deepEqual(opened, ["https://play.google.com/store/apps/details?id=com.elixirpeptide.elixirpeptide"])
        } else assert.equal(alerts[0][2], undefined)
    })
}

test("provider outage pauses protected calls only; no automatic payment replay", async t => {
    let now = 200_000
    t.mock.method(Date, "now", () => now)
    const { api, ui, count } = clientFor([[503, { code: "android_verifier_unavailable", retry_after_seconds: 60 }], [200, {}], [200, {}]])
    for (let i = 0; i < 2; i++) await assert.rejects(api.apiPost("/payments/create", {}, proof), e => ui.getErrorMessage(e) === "auth.error.playBusy")
    assert.deepEqual(count(), { proofs: 1, requests: 1 })
    await api.apiGet("/catalog")
    now += 60_000
    await api.apiPost("/payments/create", {}, proof)
    assert.deepEqual(count(), { proofs: 3, requests: 3 })
})

test("Android shares provider preparation, not tokens; recognizes native invalid-provider error code", async t => {
    t.mock.method(global, "fetch", async () => Response.json({ android_cloud_project_number: "123" }))
    let prepares = 0, requests = 0
    const api = loadTs("services/app-integrity.ts", {
        "@/services/api/request-deadline": deadlines,
        "react-native": { Platform: { OS: "android" } }, "expo-secure-store": {},
        "@/config/env": { API_BASE_URL: "https://example.test" }, "@/services/telegram/telegram-web-app": {},
        "@/services/auth/session": { getAuthTokens: () => null },
        "@expo/app-integrity": { prepareIntegrityTokenProviderAsync: async () => { prepares++; await Promise.resolve() },
            requestIntegrityCheckAsync: async () => {
                requests++
                if (requests === 3) throw Object.assign(new Error("Expired"), { code: "ERR_APP_INTEGRITY_PROVIDER_INVALID" })
                return "proof-" + requests
            } },
    })
    const [a, b] = await Promise.all([api.getAppIntegrityHeaders("payments:create"), api.getAppIntegrityHeaders("orders:create")])
    assert.equal(prepares, 1)
    assert.notEqual(a["X-App-Integrity-Token"], b["X-App-Integrity-Token"])
    assert.equal((await api.getAppIntegrityHeaders("payments:create"))["X-App-Integrity-Token"], "proof-4")
    assert.equal(prepares, 2)
})
