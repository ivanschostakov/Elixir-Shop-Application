const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

function mountChoice(request) {
    const effects = [], states = [], completions = [], cached = []
    let alert
    const component = loadTs("screens/auth/registration-program-alert.tsx", {
        react: {
            useState: value => [value, next => states.push(next)],
            useRef: value => ({ current: value }),
            useCallback: callback => callback,
            useEffect: callback => effects.push(callback),
        },
        "react-native": { Platform: { OS: "ios" }, Alert: { alert: (...args) => { alert = args } }, StyleSheet: { create: value => value } },
        "@/providers/language-provider": { useLanguage: () => ({ t: key => key }) },
        "@/hooks/use-theme-styles": { useThemeStyles: () => ({}) },
        "@/screens/auth/auth-shared.styles": { createAuthSharedStyles: () => ({}) },
        "@/services/auth/auth": { chooseRegistrationProgram: request },
        "@/services/auth/session": { cacheAuthUser: user => cached.push(user) },
    }).default
    component({ onComplete: user => completions.push(user) })
    const cleanup = effects[0]()
    effects[1]()
    return { alert, cleanup, states, completions, cached }
}

test("the native alert offers invitation, company code and 5% after registration", () => {
    const view = mountChoice(() => { throw new Error("No choice was made") })
    assert.deepEqual(view.alert[2].map(button => button.text), [
        "auth.register.haveInvitationCode", "auth.register.useCompanyCode", "auth.register.bonusProgram",
    ])
    assert.equal(view.alert[3].cancelable, false)
    view.alert[2][0].onPress()
    assert.equal(view.states.at(-1), "code")
})

test("company and bonus choices save the selected program before completing onboarding", async () => {
    for (const [button, program] of [[1, "partner"], [2, "bonus"]]) {
        const calls = [], user = { id: 1, programSelectionRequired: false }
        const view = mountChoice(async (...args) => { calls.push(args); return user })
        view.alert[2][button].onPress()
        await new Promise(resolve => setImmediate(resolve))
        assert.deepEqual(calls, [[program, undefined]])
        assert.deepEqual(view.completions, [user])
        assert.deepEqual(view.cached, [user])
    }
})

test("a failed save keeps onboarding open and does not cache a successful choice", async () => {
    const view = mountChoice(async () => { throw new Error("Unavailable") })
    view.alert[2][2].onPress()
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(view.states.at(-1), "choice")
    assert.deepEqual(view.completions, [])
    assert.deepEqual(view.cached, [])
})

test("a response arriving after logout cannot restore the previous account", async () => {
    let finish
    const view = mountChoice(() => new Promise(resolve => { finish = resolve }))
    view.alert[2][2].onPress()
    view.cleanup()
    finish({ id: 1 })
    await new Promise(resolve => setImmediate(resolve))
    assert.deepEqual(view.completions, [])
    assert.deepEqual(view.cached, [])
})
