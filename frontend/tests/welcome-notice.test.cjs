const test = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const settle = () => new Promise(resolve => setImmediate(resolve))

test("shows the awarded credit once and retries acknowledgement without another alert", async () => {
    let requests = 0, alerts = 0, acknowledgements = 0, foreground
    const native = { Platform: { OS: "android" }, Alert: { alert: () => { alerts++ } },
        AppState: { currentState: "active", addEventListener: (_, f) => { foreground = f; return { remove() {} } } } }
    const { useWelcomeNotice } = loadTs("providers/use-welcome-notice.ts", {
        react: { useRef: current => ({current}), useEffect: f => f() },
        "react-native": native, "@/i18n/translations": { translate: k => k },
        "@/services/api/benefits": {
            getWelcomeNotice: async () => { requests++; return {credit_id: 9, amount: 1000, expires_at: "2026-12-02T09:15Z"} },
            acknowledgeWelcomeNotice: async id => { assert.equal(id, 9); if (++acknowledgements === 1) throw Error("offline") },
        },
    })
    useWelcomeNotice(undefined, true)
    useWelcomeNotice(1, false)
    assert.equal(requests, 0)
    useWelcomeNotice(1, true)
    await settle()
    foreground("active")
    await settle()
    assert.deepEqual([alerts, acknowledgements], [1, 2])
})
