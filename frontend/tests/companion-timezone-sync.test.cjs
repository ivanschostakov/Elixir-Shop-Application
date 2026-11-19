const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const flush = () => new Promise(resolve => setImmediate(resolve))

test("sync at login, travel and resume; retry offline; stop at logout; never sync web", async t => {
    let tick, listener, removed = false, requests = 0, fail = true, zone = "Europe/Moscow"
    t.mock.method(global, "setInterval", callback => { tick = callback; return 1 })
    t.mock.method(global, "clearInterval", () => undefined)
    const appState = { currentState: "active", addEventListener: (_, callback) => { listener = callback; return { remove: () => { removed = true } } } }
    const platform = { OS: "ios" }
    const { startCompanionTimezoneSync } = loadTs("services/companion-timezone-sync.ts", {
        "react-native": { AppState: appState, Platform: platform },
        "@/screens/chat/companion-timezones": { deviceCompanionTimezone: () => zone },
        "@/services/api/companion": { syncCompanionTimezone: async () => { requests++; if (fail) throw Error("offline") } },
    })
    const stop = startCompanionTimezoneSync()
    await flush(); assert.equal(requests, 1)
    fail = false; tick(); await flush(); assert.equal(requests, 2)
    tick(); await flush(); assert.equal(requests, 2)
    zone = "America/Chicago"; tick(); await flush(); assert.equal(requests, 3)
    appState.currentState = "background"; zone = "Asia/Kathmandu"; tick(); await flush(); assert.equal(requests, 3)
    appState.currentState = "active"; listener("active"); await flush(); assert.equal(requests, 4)
    listener("active"); await flush(); assert.equal(requests, 5) // Another active device may have synced meanwhile.
    stop(); assert.ok(removed); tick(); listener("active"); await flush(); assert.equal(requests, 5)
    const nextAccountStop = startCompanionTimezoneSync(); await flush(); assert.equal(requests, 6); nextAccountStop()
    platform.OS = "web"; startCompanionTimezoneSync()(); await flush(); assert.equal(requests, 6)
})

test("every native API call reads fresh timezone metadata, including multipart chat", async () => {
    let zone = "Europe/Moscow"
    const requests = []
    const platform = { OS: "ios" }
    const api = loadTs("services/api/client.ts", {
        "@/services/api/constants": { API_BASE_URL: "https://example.test/api" },
        "@/services/app-integrity": { getAppIntegrityHeaders: async () => ({}), resetAppIntegrityState: async () => {} },
        "@/services/auth/session": { getAuthTokens: () => null, refreshAuthTokens: async () => null },
        "react-native": { Platform: platform },
        "@/screens/chat/companion-timezones": { deviceCompanionTimezone: () => zone },
        "@/services/api/request-deadline": { RequestDeadlineError: class extends Error {}, fetchTextWithDeadline: async (url, init) => { requests.push(init); return { response: { status: 200, ok: true }, text: "{}" } } },
    })
    await api.apiGet("/v1/users/me/ai-chat/companion")
    zone = "Asia/Kathmandu"
    await api.apiPostMultipart("/v1/users/me/ai-chat/companion/messages", new FormData())
    assert.equal(requests[0].headers.get("X-Device-Timezone"), "Europe/Moscow")
    assert.equal(requests[1].headers.get("X-Device-Timezone"), "Asia/Kathmandu")
    platform.OS = "web"; await api.apiGet("/v1/products")
    assert.equal(requests[2].headers.get("X-Device-Timezone"), null)
})
