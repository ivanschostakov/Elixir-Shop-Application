const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

function renderSelection() {
    let selection = null
    let scopeRef
    const { useCheckoutRecipientSelection } = loadTs("screens/checkout/use-checkout-recipient-selection.ts", {
        react: {
            useRef: (value) => scopeRef ??= { current: value },
            useState: () => [selection, (value) => { selection = value }],
            useCallback: (callback) => callback,
        },
    })
    return useCheckoutRecipientSelection
}

test("a saved recipient updates mounted checkout even when a basket read still shows the previous selection", async () => {
    const render = renderSelection()
    const scope = "basket:7:-9"
    const current = { id: 21, name: "Current recipient" }
    const added = { id: 22, name: "New recipient" }
    const { confirmRecipient } = render(scope, current)
    const lateRead = Promise.resolve(current)

    confirmRecipient(added)
    assert.equal(render(scope, await lateRead).recipient, added)
    assert.equal(render(scope, null).recipient, added)

    confirmRecipient(null)
    assert.equal(render(scope, added).recipient, null, "For myself does not resurrect the previous saved recipient")
    render(scope, added).confirmRecipient(current)
    assert.equal(render(scope, added).recipient, current, "Another saved recipient updates the same mounted checkout")
})

test("a response from another account or draft cannot change the current selection", () => {
    const render = renderSelection()
    const first = render("basket:7:-9", null)
    const sameAccountDraft = render("draft:7:8", null)
    const expected = { id: 22 }
    const active = render("basket:8:-10", null)
    active.confirmRecipient(expected)
    first.confirmRecipient({ id: 10 })
    sameAccountDraft.confirmRecipient(null)
    assert.equal(render("basket:8:-10", null).recipient, expected)
    assert.equal(render("draft:8:21", null).recipient, null)
})
