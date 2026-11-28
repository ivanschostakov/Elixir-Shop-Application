const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const { selectVisibleMarkers } = loadTs("utils/delivery/visible-markers.ts")
const { fetchTextWithDeadline, RequestDeadlineError } = loadTs("services/api/request-deadline.ts")

test("typing does not reapply the selected pickup address or recenter either map", () => {
    const fs = require("node:fs")
    const path = require("node:path")
    for (const file of ["delivery-screen.tsx", "delivery-screen.web.tsx"]) {
        const source = fs.readFileSync(path.join(__dirname, "../screens/delivery", file), "utf8")
        const effect = source.split("if (!pickupPoint || doorDeliveryPoint)")[1]?.split("])")[0]
        assert.ok(effect?.includes("setSearch(getPickupPointAddress"), file)
        const deps = effect.split("}, [")[1].split(",").map(name => name.trim())
        assert.ok(deps.includes("pickupPointDraft"), file)
        assert.ok(deps.every(name => !["search", "clearResults", "runSearch", "results", "isLoading"].includes(name)), file)
    }
})

test("selected pickup stays hidden while editing, including empty results, and returns on dismissal", () => {
    let cursor = 0, response = {}
    const state = []
    const { useDeliveryFlowController } = loadTs("screens/delivery/use-delivery-flow-controller.ts", {
        react: {
            useMemo: fn => fn(),
            useState(initial) {
                const i = cursor++
                if (!(i in state)) state[i] = initial
                return [state[i], value => { state[i] = value }]
            },
        },
        "@/services/api/delivery": { DEFAULT_DELIVERY_COUNTRY_CODE: "RU" },
        "@/screens/delivery/delivery-screen.constants": { supportsDoorDeliveryForCountry: () => true },
        "@/screens/delivery/delivery-screen.utils": {
            buildPickupPointDraft: p => p, getPickupPoint: p => p, getDoorDeliveryPoint: () => null,
        },
        "@/hooks/delivery/use-delivery-geo-search": { useDeliveryGeoSearch: () => response },
    })
    const point = { code: "NAG1", lat: 54, lon: 56 }
    function render(feedback = {}) {
        cursor = 0
        response = { isLoading: false, results: [], error: null, ...feedback }
        return useDeliveryFlowController({ selectedDeliveryPoint: point, userPoint: point })
    }
    const initial = render()
    assert.equal(initial.shouldShowPickupFooterExtension, true)
    initial.setIsSearchFocused(true)
    for (const feedback of [{}, { isLoading: true }, { results: ["another address"] }, {}, { error: "offline" }]) {
        const next = render(feedback)
        assert.equal(next.shouldShowPickupFooterExtension, false)
        assert.equal(next.pickupPointDraft, point)
    }
    render().setIsSearchFocused(false)
    assert.equal(render().shouldShowPickupFooterExtension, true)
})

test("Android delivery dock uses actual IME overlap, not a second full keyboard offset", () => {
    const { androidDockOverlap } = loadTs("screens/delivery/use-android-delivery-dock.ts", {
        "react-native": {},
    })
    const keyboard = { height: 320, screenY: 570 }
    assert.equal(androidDockOverlap(914, 914, 24, keyboard), 344)
    assert.equal(androidDockOverlap(570, 914, 24, keyboard), 0)
    assert.equal(androidDockOverlap(914, 914, 24, { height: 0, screenY: 700 }), 0)
    assert.equal(androidDockOverlap(914, 914, 24, undefined), 0)
})

test("Android delivery dock clears stale IME coordinates on hide and removes listeners", () => {
    let cursor = 0, effect
    const state = [], listeners = new Map()
    const { useAndroidDeliveryDock: renderDock } = loadTs("screens/delivery/use-android-delivery-dock.ts", {
        react: {
            useCallback: fn => fn,
            useEffect: fn => { effect = fn },
            useState: value => {
                const i = cursor++
                if (!(i in state)) state[i] = value
                return [state[i], next => { state[i] = next }]
            },
        },
        "react-native": {
            Dimensions: { get: () => ({ height: 914 }) }, Platform: { OS: "android" },
            Keyboard: {
                metrics: () => undefined,
                addListener(name, fn) { listeners.set(name, fn); return { remove: () => listeners.delete(name) } },
            },
        },
    })
    const render = () => { cursor = 0; return renderDock(24) }
    const dock = render(), cleanup = effect()
    dock.onLayout({ nativeEvent: { layout: { height: 914 } } })
    for (let i = 0; i < 2; i++) {
        listeners.get("keyboardDidShow")({ endCoordinates: { height: 320, screenY: 570 } })
        assert.equal(render().bottom, 344)
        listeners.get("keyboardDidHide")({ endCoordinates: { height: 0, screenY: 570 } })
        assert.equal(render().bottom, 0)
    }
    cleanup()
    assert.equal(listeners.size, 0)
})

test("native markers are bounded and follow the viewport", () => {
    const markers = Array.from({ length: 80000 }, (_, id) => ({ id, point: { lat: 55.75 + id / 1e7, lon: 37.61 } }))
    const local = { id: "ufa", point: { lat: 54.74, lon: 55.96 } }
    markers.push(local)
    assert.equal(selectVisibleMarkers(markers, { lat: 55.75, lon: 37.61, zoom: 12 }, 1500).length, 1500)
    assert.deepEqual(selectVisibleMarkers(markers, { ...local.point, zoom: 12 }, 1500), [local])
    assert.equal(markers.length, 80001)
})

test("markers handle antimeridian and invalid coordinates", () => {
    const good = { point: { lat: 0, lon: -179.9 } }
    const markers = [good, { point: { lat: NaN, lon: 180 } }]
    assert.deepEqual(selectVisibleMarkers(markers, { lat: 0, lon: 179.9, zoom: 8 }, 1500), [good])
})

test("timeout covers stalled body even if fetch ignores abort", async (t) => {
    t.mock.method(globalThis, "fetch", async () => ({ status: 200, text: () => new Promise(() => {}) }))
    await assert.rejects(fetchTextWithDeadline("https://example.test", {}, 15), RequestDeadlineError)
})

test("timeout covers headers", async (t) => {
    t.mock.method(globalThis, "fetch", () => new Promise(() => {}))
    await assert.rejects(fetchTextWithDeadline("https://example.test", {}, 15), RequestDeadlineError)
})

test("ordinary API calls can finish after 22 seconds but stop at two minutes", async t => {
    t.mock.timers.enable({ apis: ["setTimeout"] })
    const fetch = t.mock.method(globalThis, "fetch", () => new Promise(resolve =>
        setTimeout(() => resolve(Response.json({ accepted: true })), 22_000)))
    const slow = fetchTextWithDeadline("https://example.test/orders", {})
    t.mock.timers.tick(22_000)
    assert.equal(JSON.parse((await slow).text).accepted, true)

    fetch.mock.mockImplementation(() => new Promise(() => {}))
    const stalled = fetchTextWithDeadline("https://example.test/orders", {})
    const rejected = assert.rejects(stalled, RequestDeadlineError)
    t.mock.timers.tick(119_999)
    assert.equal(fetch.mock.calls[1].arguments[1].signal.aborted, false)
    t.mock.timers.tick(1)
    await rejected
    assert.equal(fetch.mock.calls.length, 2)
})

test("body is returned and deadline cleaned up after success", async (t) => {
    t.mock.method(globalThis, "fetch", async () => ({ status: 200, text: async () => '{"ok":true}' }))
    assert.equal((await fetchTextWithDeadline("https://example.test", {}, 100)).text, '{"ok":true}')
})

test("external cancellation cancels stalled body", async (t) => {
    const controller = new AbortController()
    t.mock.method(globalThis, "fetch", async () => ({ status: 200, text: () => new Promise(() => {}) }))
    const request = fetchTextWithDeadline("https://example.test", { signal: controller.signal }, 1000)
    controller.abort()
    await assert.rejects(request, RequestDeadlineError)
})

function renderPickupFooter(props = {}) {
    const jsx = (type, props) => ({ type, props })
    const styles = new Proxy({}, { get: (_target, name) => name })
    const { PickupPointFooterExtension } = loadTs("components/delivery/pickup-point-footer-extension.tsx", {
        react: { useEffect() {}, useState: initial => [initial, () => {}] },
        "react/jsx-runtime": { jsx, jsxs: jsx, Fragment: "Fragment" },
        "react-native": Object.fromEntries(["ActivityIndicator", "Image", "Pressable", "Text", "View"].map(name => [name, name])),
        "react-native-svg": { default: "Svg", Path: "Path" },
        "@/components/footer/sticky-footer.styles": { createStickyFooterStyles: () => styles },
        "@/screens/delivery/delivery-screen.styles": { createDeliveryScreenStyles: () => styles },
        "@/hooks/use-theme-styles": { useThemeStyles: factory => factory() },
        "@/i18n/translations": { translate: key => ({ "common.retry": "Повторить", "delivery.pickupPointChoose": "Deliver here" })[key] ?? key },
    })
    const tree = PickupPointFooterExtension({ title: "SYA6", rows: [{ key: "address", label: "Address", value: "Сёяха" }], onChoose() {}, onClose() {}, onCopyInfo() {}, ...props })
    const nodes = value => !value || typeof value !== "object" ? [] : Array.isArray(value) ? value.flatMap(nodes) : [value, ...nodes(value.props?.children)]
    return nodes(tree)
}

test("failed delivery quotes offer retry instead of claiming the pickup point can be confirmed", () => {
    let calls = 0
    const nodes = renderPickupFooter({ error: "destination_not_found", onChoose: () => calls++ })
    const action = nodes.find(node => node.type === "Pressable" && node.props.accessibilityLabel === "Повторить")
    assert.ok(action)
    assert.equal(nodes.some(node => node.type === "Text" && node.props.children === "Deliver here"), false)
    action.props.onPress()
    assert.equal(calls, 1)
})

test("delivery calculation preserves pickup details and disables duplicate taps while showing progress", () => {
    let calls = 0
    const nodes = renderPickupFooter({ isResolving: true, onChoose: () => calls++ })
    assert.ok(nodes.some(node => node.type === "Text" && node.props.children === "Сёяха"))
    assert.ok(nodes.some(node => node.type === "ActivityIndicator"))
    const action = nodes.find(node => node.type === "Pressable" && node.props.accessibilityLabel === "Deliver here")
    assert.equal(action.props.disabled, true)
    assert.deepEqual(action.props.accessibilityState, { busy: true, disabled: true })
    action.props.onPress()
    assert.equal(calls, 0)
    const ready = renderPickupFooter().find(node => node.type === "Pressable" && node.props.accessibilityLabel === "Deliver here")
    assert.equal(ready.props.disabled, false)
})
