const { test } = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const ts = require("typescript")
const loadTs = require("./load-ts.cjs")
const timezones = loadTs("screens/chat/companion-timezones.ts")

test("course header owns its own space outside the scroll and keyboard area", () => {
    const source = ts.createSourceFile("chat-screen.tsx", fs.readFileSync(path.join(__dirname, "../screens/chat/chat-screen.tsx"), "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const nodes = []
    const visit = node => { nodes.push(node); ts.forEachChild(node, visit) }
    visit(source)
    const byTestId = id => nodes.find(node => ts.isJsxElement(node) && node.openingElement.attributes.properties.some(attr => ts.isJsxAttribute(attr) && attr.name.text === "testID" && attr.initializer?.text === id))
    const tag = node => ts.isJsxElement(node) ? node.openingElement.tagName.getText(source) : ts.isJsxSelfClosingElement(node) ? node.tagName.getText(source) : null
    const ancestors = node => { const result = []; for (let p = node.parent; p; p = p.parent) result.push(p); return result }
    const header = byTestId("ai-chat-fixed-header")
    const body = byTestId("ai-chat-scroll-body")
    assert.ok(header && body)
    assert.equal(header.parent, body.parent)
    assert.ok(header.end < body.pos)
    const panel = nodes.find(node => tag(node) === "CompanionPanel")
    assert.ok(ancestors(panel).includes(header))
    assert.ok(!ancestors(panel).some(node => ["ScrollView", "KeyboardAvoidingView"].includes(tag(node))))
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
    assert.equal(styles.chatBody.flex, 1)
    assert.equal(styles.chatBody.overflow, "hidden")
})

test("timezone choices handle iPhone aliases and fixed offsets without reversing time", () => {
    for (const [input, expected] of [[" Europe/Moscow ", "Europe/Moscow"], ["МСК", "Europe/Moscow"], ["GMT+03:00", "Etc/GMT-3"], ["UTC-05:00", "Etc/GMT+5"], ["GMT", "UTC"], ["Europe/Kiev", "Europe/Kiev"], ["Asia/Calcutta", "Asia/Calcutta"], ["US/Central", "US/Central"]]) {
        assert.equal(timezones.normalizeCompanionTimezone(input), expected)
    }
    for (const input of [null, "", "Unknown/City", "UTC+99", "+05:30"]) assert.equal(timezones.normalizeCompanionTimezone(input), null)
    const options = timezones.companionTimezoneChoices("America/Chicago")
    assert.ok(options.some(option => option.value === "America/Chicago"))
    assert.ok(options.some(option => option.value === "Europe/Moscow"))
    assert.equal(new Set(options.map(option => option.value)).size, options.length)
})

test("timezone choices still work when an older iPhone cannot enumerate all zones", t => {
    t.mock.method(Intl, "supportedValuesOf", () => { throw new Error("unsupported") })
    const options = timezones.companionTimezoneChoices("Asia/Yerevan")
    assert.ok(options.some(option => option.value === "Asia/Yerevan"))
    assert.ok(options.some(option => option.value === "Europe/Moscow"))
})
