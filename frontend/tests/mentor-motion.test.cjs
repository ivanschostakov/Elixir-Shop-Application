const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

function harness() {
    const instances = new Map(), effects = [], values = []
    let slots, cursor
    const jsx = (type, props, key) => ({ type, props, key })
    const reanimated = {
        default: { View: "AnimatedView" },
        Easing: { bezier: (...points) => points }, ReduceMotion: { System: "system" },
        runOnUI: fn => fn, runOnJS: fn => fn,
        withTiming: (target, config, finish) => ({ target, config, finish }),
        cancelAnimation: value => { value.animation?.finish?.(false); value.animation = null },
        useSharedValue(initial) {
            const i = cursor++
            if (!slots[i]) {
                const shared = { current: initial, animation: null,
                    get value() { return this.current },
                    set value(next) {
                        if (next && typeof next === "object") {
                            this.animation?.finish?.(false)
                            this.animation = { ...next, from: this.current }
                        } else { this.current = next }
                    },
                }
                slots[i] = shared; values.push(shared)
            }
            return slots[i]
        },
        useAnimatedStyle: callback => ({ sample: callback }),
    }
    const react = { useEffect(callback, deps) {
        const i = cursor++
        if (!slots[i] || deps.some((value, j) => value !== slots[i].deps[j])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: callback() } })
    } }
    const module = loadTs("screens/chat/mentor-navigation.tsx", {
        react, "react/jsx-runtime": { jsx, jsxs: jsx },
        "react-native": { useWindowDimensions: () => ({ width: 400 }), View: "View", StyleSheet: { create: styles => styles, absoluteFill: { position: "absolute", top: 0, bottom: 0, left: 0, right: 0 } } },
        "react-native-reanimated": reanimated,
        "react-native-gesture-handler": { PanGestureHandler: "Gesture", State: { END: 5 } },
        "@/hooks/use-app-safe-area-insets": {}, "@/hooks/use-theme-styles": {},
        "@/components/footer/footer-nav-row": {}, "@/components/footer/sticky-footer.styles": {},
        "@/providers/theme-provider": {}, "@/screens/chat/mentor-icons": {}, "@/screens/chat/mentor-ui": {},
        "@/theme/spacing": { spacing: { xl: 32 } },
    })
    const render = (key, component, props) => {
        if (!instances.has(key)) instances.set(key, [])
        slots = instances.get(key); cursor = 0
        const tree = component(props); effects.splice(0).forEach(run => run()); return tree
    }
    const pages = module.MentorTabPages({ active: "nutrition", direction: 1, transitionKey: 0, onSelect() {}, render: name => name, footer: "footer", footerVisible: true, footerHeight: 86, onSettled() {} }).props.children
    return { render, pages: pages.props.children[0], footer: pages.props.children[1], values,
        advance(fraction) { for (const value of values) if (value.animation) {
            const animation = value.animation
            value.current = animation.from + (animation.target - animation.from) * fraction
            if (fraction === 1) { value.animation = null; animation.finish?.(true) }
        } },
    }
}

test("mentor switches directly to the selected page and reverses from the presented frame on rapid taps", () => {
    const h = harness(), pane = h.pages.find(node => node.props.page === "chat"), settled = []
    let props = { ...pane.props, active: false, direction: 1, onSettled: page => settled.push(page) }
    const render = () => h.render("chat", pane.type, props)
    const motion = () => render().props.style.at(-1).sample()
    render()
    props = { ...props, active: true }; render()
    assert.equal(motion().opacity, undefined, "UIKit glass must never inherit animated opacity"); assert.equal(motion().transform[0].translateX, 400)
    assert.ok(h.values.some(value => value.animation))
    for (const value of h.values) if (value.animation) {
        assert.equal(value.animation.config.duration, 240); assert.equal(value.animation.config.reduceMotion, "system")
    }
    h.advance(0.4)
    const beforeReverse = motion()
    props = { ...props, active: false, direction: -1 }; render()
    assert.deepEqual(motion(), beforeReverse, "A rapid back action must not reset translation or opacity")
    h.advance(0.5)
    const interrupted = motion()
    props = { ...props, active: true, direction: 1 }; render()
    assert.deepEqual(motion(), interrupted)
    h.advance(1)
    assert.deepEqual(motion(), { transform: [{ translateX: 0 }] })
    assert.deepEqual(settled, ["chat"])
})

test("the footer moves out as an overlay and never changes the page viewport height", () => {
    const h = harness(), footer = h.footer
    let props = { ...footer.props, visible: true }
    const render = () => h.render("footer", footer.type, props)
    const tree = render()
    assert.equal(tree.props.style[0].position, "absolute")
    props = { ...props, visible: false }
    const hidden = render()
    assert.equal(hidden.props.pointerEvents, "none"); assert.equal(hidden.props.accessibilityElementsHidden, true)
    h.advance(0.5)
    const beforeReverse = hidden.props.style.at(-1).sample()
    assert.equal(beforeReverse.transform[0].translateY, 59)
    props = { ...props, visible: true }
    assert.deepEqual(render().props.style.at(-1).sample(), beforeReverse)
    h.advance(1)
    assert.equal(render().props.style.at(-1).sample().transform[0].translateY, 0)
    assert.equal(h.pages.length, 5, "Retained pages, including settings, keep their geometry and drafts")
})
