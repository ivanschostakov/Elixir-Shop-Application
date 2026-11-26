const test = require("node:test")
const assert = require("node:assert/strict")
const load = require("./load-ts.cjs")
const jsx = (type, props) => ({ type, props })
const runtime = { jsx, jsxs: jsx, Fragment: "Fragment" }
const react = { useCallback: fn => fn }
const base = { "react/jsx-runtime": runtime, react }

test("shared icon buttons preserve the same action and disabled state on both renderers", () => {
    for (const native of [null, "UIKitButton"]) {
        let presses = 0
        const { AppIconButton } = load("components/platform/app-icon-button.tsx", { ...base,
            "react-native": { Pressable: "Pressable", View: "View", Text: "Text", ActivityIndicator: "Spinner", StyleSheet: { create: x => x } },
            "react-native-svg": { default: "Svg", Path: "Path" },
            "@/assets/icons/chat/attachment-svgrepo-com.svg": { default: "Attachment" },
            "@/assets/icons/mentor/settings.svg": { default: "Settings" },
            "@/components/platform/composer-action": { AdminComposerAction: "Composer" },
            "@/components/platform/native-controls": { NativeChatAction: native, nativeControlsAvailable: !!native },
        })
        const button = AppIconButton({ action: "back", label: "Back", onPress: () => presses++, disabled: true, dark: false })
        assert.equal(button.props.disabled, true)
        assert.equal(native ? button.props.label : button.props.accessibilityLabel, "Back")
        assert.equal(button.type, native ?? "Pressable")
        const enabled = AppIconButton({ action: "back", label: "Back", onPress: () => presses++, dark: false })
        ;(native ? enabled.props.onAction : enabled.props.onPress)()
        assert.equal(presses, 1)
        const busy = AppIconButton({ action: "busy", label: "Sending", onPress: () => {}, dark: false, appearance: "composer", transcribing: true })
        assert.equal(native ? busy.props.action : busy.props.children.props.busy, native ? "busy" : true)
    }
})

test("shared surfaces use glass when available, blur on older iOS and a themed Android surface", () => {
    for (const [platform, installed, available, expected] of [["ios", true, true, "Glass"], ["ios", true, false, "Blur"], ["ios", false, false, "Blur"], ["android", false, false, "View"]]) {
        let probes = 0
        const { AppSurface } = load("components/platform/app-surface.tsx", { ...base,
            expo: { requireOptionalNativeModule: () => { probes++; return installed ? {} : null } },
            "react-native": { Platform: { OS: platform }, View: "View", StyleSheet: { absoluteFill: {} } },
            "expo-blur": { BlurView: "Blur" },
            "expo-glass-effect": { GlassView: "Glass", isLiquidGlassAvailable: () => available, isGlassEffectAPIAvailable: () => available },
            "react-native-reanimated": {},
        })
        const surface = AppSurface({ dark: true, fallbackColor: "#263040", radius: 29, children: "Content" })
        assert.equal(surface.type, expected)
        assert.equal(surface.props.children, "Content")
        if (expected === "Glass") assert.equal(surface.props.colorScheme, "dark")
        if (expected === "Blur") assert.equal(surface.props.tint, "systemThinMaterialDark")
        if (platform === "android") { assert.equal(probes, 0); assert.equal(surface.props.style[1].backgroundColor, "#263040") }
    }
})

test("form adapters preserve keyboard behavior, offsets and the chat's disabled avoider", () => {
    for (const platform of ["ios", "android"]) {
        const { AppFormLayout } = load("components/platform/app-form-layout.tsx", { ...base,
            "react-native": { Platform: { OS: platform }, KeyboardAvoidingView: "Avoider" },
        })
        const form = AppFormLayout({ iosOffset: 12, enabled: false, children: "Form" })
        assert.equal(form.props.behavior, platform === "ios" ? "padding" : "height")
        assert.equal(form.props.keyboardVerticalOffset, platform === "ios" ? 12 : 0)
        assert.equal(form.props.enabled, false)
        assert.equal(form.props.children, "Form")
        if (platform === "android") assert.equal(AppFormLayout({ androidBehavior: null }).props.behavior, undefined)
    }
})

for (const platform of ["ios", "android"]) test(`${platform} builds use a native history menu and ignore unavailable actions`, () => {
    const selected = []
    const { AppMenu } = load("components/platform/app-menu.tsx", { ...base,
        "react-native": { Platform: { OS: platform }, View: "View", Text: "Text", StyleSheet: { create: x => x, absoluteFill: {} } },
        "react-native-svg": { default: "Svg", Path: "Path" },
        "./native-menu-view": { MenuView: "Menu" },
        "@/components/platform/app-surface": { AppSurface: "Surface" },
        "@/components/platform/app-action-sheet": { useAppActionSheet: () => () => {} },
    })
    const menu = AppMenu({ label: "History", dark: false, options: [{ id: "12", label: "Order", detail: "Closed" }, { id: "13", label: "Unavailable", disabled: true }], value: "12", onChange: id => selected.push(id) })
    assert.equal(menu.props.actions[0].title, platform === "android" ? "✓ Order · Closed" : "Order")
    menu.props.onPressAction({ nativeEvent: { event: "unknown" } })
    menu.props.onPressAction({ nativeEvent: { event: "13" } })
    menu.props.onPressAction({ nativeEvent: { event: "12" } })
    assert.deepEqual(selected, ["12"])
})

test("shared action sheets map selections, cancellation and disabled actions consistently", () => {
    let config, callback, selected = 0, closed = 0
    const { useAppActionSheet } = load("components/platform/app-action-sheet.tsx", { ...base,
        "@expo/react-native-action-sheet": { useActionSheet: () => ({ showActionSheetWithOptions: (options, onSelect) => { config = options; callback = onSelect } }) },
        "@/providers/language-provider": { useLanguage: () => ({ t: () => "Cancel" }) },
        "@/providers/theme-provider": { useTheme: () => ({ isDark: true, palette: { surface: "#222", text: "#FFF" } }) },
    })
    useAppActionSheet()({ actions: [{ id: "gallery", label: "Gallery", onPress: () => selected++ }, { id: "camera", label: "Camera", disabled: true, onPress: () => selected++ }], onClose: () => closed++ })
    assert.deepEqual(config.options, ["Gallery", "Camera", "Cancel"])
    assert.equal(config.userInterfaceStyle, "dark")
    assert.equal(config.useModal, true)
    callback(config.cancelButtonIndex); callback(undefined); callback(1)
    assert.equal(selected, 0)
    callback(0)
    assert.equal(selected, 1)
    assert.equal(closed, 4)
})

for (const platform of ["web", "android"]) test(`${platform} history opens a selection sheet when the native menu is unavailable`, () => {
    let sheet, selection
    const { AppMenu } = load("components/platform/app-menu.tsx", { ...base,
        "./native-menu-view": { MenuView: null },
        "react-native": { Platform: { OS: platform }, Pressable: "Button", View: "View", Text: "Text", StyleSheet: { create: x => x, absoluteFill: {} } },
        "react-native-svg": { default: "Svg", Path: "Path" },
        "@/components/platform/app-surface": { AppSurface: "Surface" },
        "@/components/platform/app-action-sheet": { useAppActionSheet: () => options => { sheet = options } },
    })
    const menu = AppMenu({ label: "History", dark: false, options: [{ id: "12", label: "Order", detail: "Closed" }], onChange: id => { selection = id } })
    assert.equal(menu.type, "Button")
    menu.props.onPress()
    assert.equal(sheet.actions[0].label, "Order · Closed")
    sheet.actions[0].onPress()
    assert.equal(selection, "12")
})

test("picker changes commit only on Done; cancellation discards the draft and follows the current selection", () => {
    const slots = [], effects = [], changes = []
    let cursor = 0
    const hooks = {
        useState(initial) {
            const i = cursor++
            if (!(i in slots)) slots[i] = initial
            return [slots[i], value => { slots[i] = value }]
        },
        useEffect(fn, deps) {
            const i = cursor++
            if (!slots[i] || deps.some((value, j) => value !== slots[i][j])) {
                slots[i] = deps
                effects.push(fn)
            }
        },
    }
    const nodes = tree => !tree || typeof tree !== "object" ? [] : Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)]
    const Picker = Object.assign(function Picker() {}, { Item: "PickerItem" })
    const { AppPickerSheetField, AppPickerPanel } = load("components/platform/app-picker.tsx", { ...base, react: hooks,
        "react-native": { Modal: "Modal", Pressable: "Button", Text: "Text", View: "View" },
        "@react-native-picker/picker": { Picker },
        "react-native-safe-area-context": { useSafeAreaInsets: () => ({ bottom: 34 }) },
        "@/components/content/content.styles": { createContentStyles() {} },
        "@/hooks/use-theme-styles": { useThemeStyles: () => ({}) },
        "@/providers/language-provider": { useLanguage: () => ({ t: key => key }) },
        "@/theme/spacing": { spacing: { lg: 20, sm: 8 } },
    })
    const props = { label: "Sort", title: "Sort", selectedValue: "newest", valueLabel: "Newest", options: [{ key: "new", label: "Newest", value: "newest" }, { key: "price", label: "Price", value: "price" }], onChange: value => changes.push(value) }
    const render = () => {
        cursor = 0
        const tree = AppPickerSheetField(props)
        effects.splice(0).forEach(fn => fn())
        return nodes(tree)
    }
    const find = type => render().find(node => node.type === type)
    find("Button").props.onPress()
    find(Picker).props.onValueChange("price")
    assert.deepEqual(changes, [])
    find(AppPickerPanel).props.onCancel()
    find("Button").props.onPress()
    assert.equal(find(Picker).props.selectedValue, "newest")
    find(Picker).props.onValueChange("price")
    find(AppPickerPanel).props.onConfirm()
    assert.deepEqual(changes, ["price"])
    assert.equal(find("Modal").props.visible, false)
    props.selectedValue = "price"
    find("Button").props.onPress()
    assert.equal(find(Picker).props.selectedValue, "price")
    find(Picker).props.onValueChange("newest")
    find("Modal").props.onRequestClose()
    find("Button").props.onPress()
    assert.equal(find(Picker).props.selectedValue, "price")
    assert.deepEqual(changes, ["price"])
})

test("native level sliders save only deliberate touches and report each bounded level while dragging", () => {
    for (const platform of ["ios", "android"]) {
        const changes = []
        const { AppLevelSlider } = load("components/platform/app-level-slider.tsx", {
            ...base, react: { useRef: value => ({ current: value }) },
            "react-native": { Platform: { OS: platform }, View: "View", StyleSheet: { create: value => value } },
            "@react-native-community/slider": { default: "SystemSlider" },
        })
        const props = { label: "Energy", value: null, maximum: 5, valueText: "Move the slider", onChange: value => changes.push(value), color: "green", trackColor: "gray" }
        const slider = AppLevelSlider(props).props.children
        assert.equal(slider.type, "SystemSlider")
        assert.equal(slider.props.accessibilityValue.now, undefined)
        assert.deepEqual(changes, [], "the midpoint is not a guessed health record")
        slider.props.onSlidingStart(3)
        slider.props.onValueChange(4.1)
        slider.props.onValueChange(4.2)
        slider.props.onSlidingComplete(4)
        assert.deepEqual(changes, [3, 4])
        slider.props.onValueChange(NaN)
        slider.props.onValueChange(99)
        assert.deepEqual(changes, [3, 4, 5])
        const disabled = AppLevelSlider({ ...props, disabled: true }).props.children
        disabled.props.onSlidingStart(2)
        assert.deepEqual(changes, [3, 4, 5])
    }
})

test("Play slider leaves an unanswered score empty and supports drag and accessibility adjustments", () => {
    const changes = []
    const { AppLevelSlider } = load("components/platform/app-level-slider.android.play.tsx", {
        ...base, react: { useRef: value => ({ current: value }), useState: () => [120, () => {}] },
        "react-native": { View: "View", StyleSheet: { create: value => value } },
    })
    const props = { label: "Energy", value: null, maximum: 5, valueText: "Select", onChange: value => changes.push(value) }
    const slider = AppLevelSlider(props).props
    assert.equal(slider.accessibilityValue.now, undefined)
    assert.deepEqual(changes, [])
    slider.onResponderGrant({ nativeEvent: { locationX: 60 } })
    slider.onResponderMove({ nativeEvent: { locationX: 61 } })
    slider.onResponderMove({ nativeEvent: { locationX: 140 } })
    slider.onResponderMove({ nativeEvent: { locationX: -1 } })
    slider.onAccessibilityAction({ nativeEvent: { actionName: "increment" } })
    assert.deepEqual(changes, [3, 5, 1, 4])
    const disabled = AppLevelSlider({ ...props, disabled: true }).props
    assert.equal(disabled.onStartShouldSetResponder(), false)
    disabled.onAccessibilityAction({ nativeEvent: { actionName: "decrement" } })
    assert.equal(changes.length, 4)
})

test("step transitions reverse from the presented positions on rapid Back taps without fading native controls", () => {
    const instances = new Map(), effects = [], values = []
    let slots, cursor
    const hooks = { useEffect(fn, deps) { const i = cursor++; if (!slots[i] || deps.some((value, j) => value !== slots[i].deps[j])) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: fn() } }) } }
    const reanimated = {
        default: { View: "AnimatedView" }, Easing: { bezier: () => "easing" }, ReduceMotion: { System: "system" },
        runOnUI: fn => fn, withTiming: (target, config) => ({ target, config }), cancelAnimation: value => { value.animation = null },
        useSharedValue(initial) {
            const i = cursor++
            if (!slots[i]) {
                const value = { current: initial, animation: null, get value() { return this.current }, set value(next) { if (typeof next === "object") this.animation = { ...next, from: this.current }; else { this.current = next; this.animation = null } } }
                slots[i] = value; values.push(value)
            }
            return slots[i]
        },
        useAnimatedStyle: sample => ({ sample }),
    }
    const { AppStepTransition } = load("components/platform/app-step-transition.tsx", {
        ...base, react: hooks, "react-native": { View: "View", StyleSheet: { create: value => value, absoluteFill: {} } }, "react-native-reanimated": reanimated,
    })
    const render = (step, direction) => AppStepTransition({ step, direction, count: 6, render: index => `Page ${index}` }).props.children.map((pane, index) => {
        slots = instances.get(index) ?? []; instances.set(index, slots); cursor = 0
        const result = pane.type(pane.props); effects.splice(0).forEach(fn => fn()); return result
    })
    const advance = fraction => { for (const value of values) if (value.animation) value.current = value.animation.from + (value.animation.target - value.animation.from) * fraction }
    render(0, 1); render(1, 1); advance(0.4)
    const before = render(1, 1).map(pane => pane.props.style.at(-1).sample())
    const reverse = render(0, -1).map(pane => pane.props.style.at(-1).sample())
    assert.deepEqual(reverse, before)
    assert.ok(reverse.every(style => style.opacity === undefined))
    for (const value of values.filter(value => value.animation)) {
        assert.equal(value.animation.config.duration, 240)
        assert.equal(value.animation.config.reduceMotion, "system")
    }
    advance(1)
    assert.equal(render(0, -1)[0].props.style.at(-1).sample().transform[0].translateX, "0%")
})
