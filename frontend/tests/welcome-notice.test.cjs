const test = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const settle = () => new Promise(resolve => setImmediate(resolve))

test("shows the awarded credit once and retries acknowledgement without another alert", async () => {
    let requests = 0, alerts = 0, acknowledgements = 0, foreground, remind, permissionPrompts = 0
    const native = { Platform: { OS: "android" }, Alert: { alert: (_, __, buttons) => { alerts++; assert.equal(buttons.length, 1); remind = buttons[0].onPress } },
        AppState: { currentState: "active", addEventListener: (_, f) => { foreground = f; return { remove() {} } } } }
    const { useWelcomeNotice } = loadTs("providers/use-welcome-notice.ts", {
        react: { useRef: current => ({current}), useEffect: f => f() },
        "react-native": native, "@/i18n/translations": { translate: k => k },
        "@/services/notifications/startup-notices": loadTs("services/notifications/startup-notices.ts", { "react-native": native }),
        "@/services/auth/session": { getAuthTokens: () => null },
        "@/services/notifications/order-status-notifications": { syncOrderStatusNotifications: ({requestPermissions}) => {
            assert.equal(requestPermissions, true); permissionPrompts++
        } },
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
    assert.equal(permissionPrompts, 0)
    remind()
    await settle()
    foreground("active")
    await settle()
    assert.deepEqual([alerts, acknowledgements], [1, 2])
    assert.equal(permissionPrompts, 1)
})

test("already acknowledged credit enrolls without a button; no token falls back to the daily notice", async () => {
    for (const token of [null, "registered"]) {
        let prompts = 0, claims = 0, alerts = 0
        const native = { Platform:{OS:"android"}, AppState:{currentState:"active", addEventListener:()=>({remove(){}})},
            Alert:{alert:(title,body)=>{alerts++;assert.equal(title,"Title");assert.equal(body,"Body")}} }
        const {useWelcomeNotice: runHook} = loadTs("providers/use-welcome-notice.ts", {
            react: {useRef: current => ({current}), useEffect: cb => cb()},
            "react-native": native,
            "@/services/notifications/startup-notices": loadTs("services/notifications/startup-notices.ts", { "react-native": native }),
            "@/services/auth/session": { getAuthTokens: () => null },
            "@/i18n/translations": {translate:k=>k},
            "@/services/api/benefits": {getWelcomeNotice:async()=>null,claimWelcomeReminder:async()=>{claims++;return {title:"Title",body:"Body"}}},
            "@/services/notifications/order-status-notifications": {syncOrderStatusNotifications:async opts=>{
                prompts++;assert.deepEqual(opts,{requestPermissions:true,automatic:true});return token
            }},
        })
        runHook(1,true)
        await settle()
        assert.deepEqual([prompts,claims,alerts],token ? [1,0,0] : [1,1,1])
    }
})
