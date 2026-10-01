/* global __dirname */
const { test } = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const ts = require("typescript")
const loadTs = require("./load-ts.cjs")
const timezones = loadTs("screens/chat/companion-timezones.ts")

test("stationary chat chrome sits above retained content with an in-flow keyboard composer", () => {
    const source = ts.createSourceFile("chat-screen.tsx", fs.readFileSync(path.join(__dirname, "../screens/chat/chat-screen.tsx"), "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const nodes = []
    const visit = node => { nodes.push(node); ts.forEachChild(node, visit) }
    visit(source)
    const byTestId = id => nodes.find(node => ts.isJsxElement(node) && node.openingElement.attributes.properties.some(attr => ts.isJsxAttribute(attr) && attr.name.text === "testID" && attr.initializer?.text === id))
    const tag = node => ts.isJsxElement(node) ? node.openingElement.tagName.getText(source) : ts.isJsxSelfClosingElement(node) ? node.tagName.getText(source) : null
    const ancestors = node => { const result = []; for (let p = node.parent; p; p = p.parent) result.push(p); return result }
    const header = byTestId("ai-chat-fixed-header")
    const body = byTestId("ai-chat-scroll-body")
    const composer = byTestId("ai-chat-composer-dock")
    assert.ok(header && body && composer)
    assert.ok(header.end < body.pos)
    const backdrop = nodes.find(node => tag(node) === "ChatBackdrop")
    assert.ok(backdrop.end < header.pos)
    assert.ok(!ancestors(backdrop).some(node => ["ChatKeyboardLayout", "ChatModePane", "ChatModeTransition"].includes(tag(node))), "Wallpaper never resizes with the keyboard or animates with a mode")
    const panel = nodes.find(node => tag(node) === "CompanionPanel")
    assert.ok(ancestors(panel).includes(composer), "Mentor navigation stays inside the composer when conditionally shown")
    assert.ok(!ancestors(panel).includes(header))
    assert.ok(!ancestors(panel).some(node => tag(node) === "ScrollView"))
    const input = nodes.find(node => tag(node) === "ChatComposerInput")
    assert.ok(input, "Use the bounded production composer input")
    assert.ok(panel.end < input.pos)
    const toggle = nodes.find(node => tag(node) === "MentorModeToggle")
    assert.ok(toggle && ancestors(toggle).includes(composer), "Mentor toggle stays in the shortcut row above the input")
    assert.ok(!ancestors(toggle).includes(header))
    assert.ok(toggle.end < input.pos)
    const keyboard = nodes.find(node => tag(node) === "ChatKeyboardLayout")
    assert.ok(keyboard, "Use the same production shell exercised by the browser fixture")
    assert.ok(ancestors(header).includes(keyboard), "A fullscreen shared keyboard shell includes the header's screen offset")
    assert.ok(!ancestors(header).some(node => ["ChatModeTransition", "ChatModePane"].includes(tag(node))))
    assert.equal(nodes.filter(node => tag(node) === "ChatModePane").length, 3)
    assert.equal(nodes.filter(node => tag(node) === "ChatKeyboardLayout").length, 1, "All chat modes share one keyboard resize")
    assert.ok(ancestors(body).includes(keyboard))
    assert.ok(ancestors(composer).includes(body))
    assert.ok(!ancestors(composer).some(node => tag(node) === "ScrollView"))
    assert.ok(!nodes.some(node => tag(node) === "KeyboardAvoidingView"), "Do not add a second keyboard avoidance layer")
    const composerStyle = composer.openingElement.attributes.properties.find(attr => attr.name?.text === "style").getText(source)
    assert.match(composerStyle, /composerDockInFlow/)
    const focus = input.attributes.properties.find(attr => attr.name?.text === "onFocus")
    assert.ok(!focus || !/setMentorPage\(null\)/.test(focus.getText(source)), "Focusing input must preserve the open mentor form")
    const { createChatScreenStyles } = loadTs("screens/chat/chat-screen.styles.ts", {
        "react-native": { StyleSheet: { create: value => value, absoluteFillObject: { position: "absolute" } } },
        "@/theme/spacing": { spacing: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 } },
    })
    const styles = createChatScreenStyles({})
    assert.equal(styles.fixedHeader.flexShrink, 0)
    assert.notEqual(styles.fixedHeader.position, "absolute")
    assert.notEqual(styles.topBarRow.position, "absolute")
    const dock = { ...styles.composerDock, ...styles.mentorComposerDock, ...styles.composerDockInFlow }
    assert.notEqual(dock.position, "absolute", "The AI composer reserves real space above the keyboard")
    assert.equal(dock.flexShrink, 0)
    assert.equal(styles.chatBody.flex, 1)
    assert.equal(styles.chatBody.minHeight, 0)
    assert.equal(styles.chatBody.overflow, "hidden")
    assert.equal(styles.messagesScroll.flex, 1)
    assert.equal(styles.messagesScroll.minHeight, 0)
})

test("iOS keyboard avoidance resizes the screen instead of translating its scroll area", () => {
    const renderShell = platform => {
        const { ChatKeyboardLayout } = loadTs("screens/chat/chat-keyboard-layout.tsx", {
            "react-native": { KeyboardAvoidingView: "KeyboardAvoidingView", Platform: { OS: platform }, StyleSheet: { create: value => value } },
        })
        return ChatKeyboardLayout({ children: "chat content" })
    }
    const ios = renderShell("ios")
    assert.equal(ios.type, "KeyboardAvoidingView")
    assert.equal(ios.props.behavior, "padding")
    assert.equal(ios.props.keyboardVerticalOffset ?? 0, 0, "Fullscreen shell uses screen coordinates without double-counting header height")
    assert.equal(ios.props.contentContainerStyle, undefined, "A translated content wrapper must not return")
    const android = renderShell("android")
    assert.ok(android.props.enabled === false || android.props.behavior === undefined, "Android's native resize must not be applied a second time")
})

test("automatic timezone handles iPhone aliases and exact fractional offsets", () => {
    for (const [input, expected] of [[" Europe/Moscow ", "Europe/Moscow"], ["МСК", "Europe/Moscow"], ["GMT+03:00", "Etc/GMT-3"], ["UTC-05:00", "Etc/GMT+5"], ["GMT", "UTC"], ["Europe/Kiev", "Europe/Kiev"], ["Asia/Calcutta", "Asia/Calcutta"], ["US/Central", "US/Central"]]) {
        assert.equal(timezones.normalizeCompanionTimezone(input), expected)
    }
    for (const input of [null, "", "Unknown/City", "UTC+99", "UTC+14:30", "UTC+05:99"]) assert.equal(timezones.normalizeCompanionTimezone(input), null)
    assert.equal(timezones.normalizeCompanionTimezone("+05:30"), "UTC+05:30")
    assert.equal(timezones.normalizeCompanionTimezone("GMT+05:45"), "UTC+05:45")
    assert.equal(timezones.normalizeCompanionTimezone("UTC-03:30"), "UTC-03:30")
})

test("missing IANA information falls back to the phone offset, not Moscow", t => {
    t.mock.method(Intl, "DateTimeFormat", () => { throw new Error("unsupported") })
    t.mock.method(Date.prototype, "getTimezoneOffset", () => -345)
    assert.equal(timezones.deviceCompanionTimezone(), "UTC+05:45")
})

test("history and editing follow device timezone without mutating saved instants", t => {
    const previous = process.env.TZ
    t.after(() => { if (previous === undefined) delete process.env.TZ; else process.env.TZ = previous })
    const original = "2026-09-02T21:30:42.123Z"
    process.env.TZ = "Europe/Moscow"
    assert.equal(timezones.localDateTime(original), "2026-09-03 00:30")
    const oldClock = timezones.deviceClockKey()
    process.env.TZ = "America/Chicago"
    assert.equal(timezones.localDateTime(original), "2026-09-02 16:30")
    assert.notEqual(timezones.deviceClockKey(), oldClock)
    assert.equal(timezones.deviceCompanionTimezone(), "America/Chicago")
    assert.equal(timezones.localEntryTimestamp("2026-09-02 16:30", original), original)
    assert.equal(timezones.localEntryTimestamp("2026-09-02 17:30", original), "2026-09-02T22:30:00.000Z")
    assert.throws(() => timezones.localEntryTimestamp("2026-02-30 17:30", original))
    assert.throws(() => timezones.localEntryTimestamp("2026-03-08 02:30", original)) // DST gap
    const secondAutumnHour = "2026-11-01T07:30:17Z"
    assert.equal(timezones.localEntryTimestamp("2026-11-01 01:30", secondAutumnHour), secondAutumnHour)
    process.env.TZ = "Asia/Kathmandu"
    assert.equal(timezones.localDateTime(original), "2026-09-03 03:15")
    assert.equal(timezones.localEntryTimestamp("2026-09-03 03:15", original), original)
})

test("no timezone selector, raw offset entry or server-zone display remains", () => {
    const source = fs.readFileSync(path.join(__dirname, "../screens/chat/companion.tsx"), "utf8")
    assert.doesNotMatch(source, /TimezoneField|setTimezone|Выберите часовой пояс|Поиск города|Дата и время с часовым поясом/)
    assert.match(source, /useDeviceClock\(\)/)
    assert.match(source, /localEntryTimestamp\(entryDateText, entry.occurred_at\)/)
    assert.match(source, /\[focused, enabled, refresh, clock\]/)
    assert.match(source, /if \(focused && enabled\) void refresh\(\)/)
    assert.match(source, /\[c.clock\]/)
    assert.doesNotMatch(source, /dateLabel\([^)]*settings|timeZone: profile|calendarDate\(zone/)
    assert.match(source, /dateLabel\(entry.occurred_at, clock\)/)
    assert.match(source, /clock=\{c.clock\}/)
})

test("memoized date labels explicitly depend on the current phone clock", () => {
    const instant = "2026-09-02T21:30:42Z"
    assert.match(timezones.formatCompanionDate(instant, "Europe/Moscow|-180|2026-09-03"), /03\.09\.2026.*00:30/)
    assert.match(timezones.formatCompanionDate(instant, "America/Chicago|300|2026-09-02"), /02\.09\.2026.*16:30/)
    assert.match(timezones.formatCompanionDate(instant, "UTC+05:45|-345|2026-09-03"), /03\.09\.2026.*03:15/)
})
