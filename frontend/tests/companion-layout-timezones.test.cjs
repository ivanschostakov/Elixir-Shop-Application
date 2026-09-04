const { test } = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const ts = require("typescript")
const loadTs = require("./load-ts.cjs")
const timezones = loadTs("screens/chat/companion-timezones.ts")

test("course actions are pinned directly above the input and stay outside message scrolling", () => {
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
    assert.equal(header.parent, body.parent)
    assert.ok(header.end < body.pos)
    const panel = nodes.find(node => tag(node) === "CompanionPanel")
    assert.equal(panel.parent, composer)
    assert.ok(ancestors(panel).some(node => tag(node) === "KeyboardAvoidingView"))
    assert.ok(!ancestors(panel).includes(header))
    assert.ok(!ancestors(panel).some(node => tag(node) === "ScrollView"))
    const input = nodes.find(node => tag(node) === "TextInput")
    assert.ok(panel.end < input.pos)
    assert.match(composer.openingElement.attributes.properties.find(attr => attr.name?.text === "onLayout").getText(source), /setComposerHeight/)
    const keyboard = nodes.find(node => tag(node) === "KeyboardAvoidingView")
    assert.ok(ancestors(keyboard).includes(body))
    assert.ok(!ancestors(keyboard).includes(header))
    assert.equal(keyboard.openingElement.attributes.properties.find(attr => attr.name?.text === "keyboardVerticalOffset").initializer.expression.getText(source), "chatHeaderHeight")
    assert.match(header.openingElement.attributes.properties.find(attr => attr.name?.text === "onLayout").getText(source), /setChatHeaderHeight/)
    const { createChatScreenStyles } = loadTs("screens/chat/chat-screen.styles.ts", {
        "react-native": { StyleSheet: { create: value => value, absoluteFillObject: { position: "absolute" } } },
        "@/theme/spacing": { spacing: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32 } },
    })
    const styles = createChatScreenStyles({})
    assert.equal(styles.fixedHeader.flexShrink, 0)
    assert.notEqual(styles.fixedHeader.position, "absolute")
    assert.notEqual(styles.topBarRow.position, "absolute")
    assert.equal(styles.composerDock.position, "absolute")
    assert.equal(styles.chatBody.flex, 1)
    assert.equal(styles.chatBody.overflow, "hidden")
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
    assert.match(source, /\[focused, refresh, clock\]/)
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
