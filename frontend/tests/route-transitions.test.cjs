const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

const routes = loadTs("constants/routes.ts")

test("each native surface resolves its own path instead of the incoming global path", () => {
    const { getScreenPathname } = loadTs("components/navigation/route-screen-path.ts")
    assert.equal(getScreenPathname("index"), "/")
    assert.equal(getScreenPathname("chat"), "/chat")
    assert.equal(getScreenPathname("(protected)"), null)
    assert.equal(getScreenPathname("(guest)"), null)
    assert.equal(getScreenPathname("products/[id]", { id: "123" }), "/products/123")
    assert.equal(getScreenPathname("(protected)/profile"), "/profile")
})

test("chat has fullscreen geometry before its effects or requests finish", () => {
    const { getDefaultScreenChromeTemplate } = loadTs("components/navigation/screen-template-registry.ts", {
        "@/constants/routes": routes,
    })
    for (const authenticated of [false, true]) {
        assert.deepEqual(getDefaultScreenChromeTemplate("/chat", authenticated), {
            footer: "none", header: "none", mode: "fullscreen", title: routes.getRouteTitle("/chat"),
        })
    }
    assert.equal(getDefaultScreenChromeTemplate("/basket", true).footer, "nav+basketAction")
})

test("a screen keeps its chrome through blur until its native transition unmounts it", () => {
    const effects = []
    let template = null
    const override = { header: "none", footer: "none", mode: "fullscreen" }
    const { useApplyScreenTemplate } = loadTs("components/templates/screen-template.hooks.ts", {
        react: { useLayoutEffect: effect => effects.push(effect), useRef: value => ({ current: value }) },
        "@/providers/screen-chrome-template-provider": {
            useScreenChromeTemplate: () => ({ setScreenChromeTemplate: value => { template = value } }),
        },
        "@/providers/screen-template-provider": { useScreenTemplate: () => ({ setScreenTemplate: () => {} }) },
        // Focus changes must not reset the outgoing screen to default geometry.
        "expo-router": { useFocusEffect: () => { throw new Error("chrome must be owned by the screen lifetime") } },
    })
    useApplyScreenTemplate("feed", override)
    const cleanups = effects.map(effect => effect())
    assert.equal(template, override)
    // Unmount after the native transition, rather than blur when it starts.
    cleanups.forEach(cleanup => cleanup())
    assert.equal(template, null)
})

test("native route chrome and body start fully visible instead of adding independent entrance fades", () => {
    const effects = []
    const values = []
    const context = {}
    const { useEntranceAnimation } = loadTs("hooks/animation/use-entrance-animation.ts", {
        react: {
            useContext: value => { assert.equal(value, context); return true },
            useEffect: effect => effects.push(effect),
            useRef: value => ({ current: value }),
        },
        "react-native": {
            Platform: { OS: "ios" },
            Animated: {
                Value: class {
                    constructor(value) { values.push(value) }
                    setValue(value) { values.push(value) }
                    interpolate() { return 0 }
                },
                timing: () => { throw new Error("a second animation must not start") },
            },
        },
        "@/theme/motion": { motion: { duration: { enter: 180 }, easing: { enter: null } } },
        "@/components/navigation/route-transition-context": { NativeRouteTransitionContext: context },
    })
    useEntranceAnimation()
    effects.forEach(effect => effect())
    assert.deepEqual(values, [1, 1])
})
