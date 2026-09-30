const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const { filterBlockedCommunityMessages } = loadTs("hooks/chat/community-blocks.ts")

test("blocking hides cached messages and quoted text without changing other messages", () => {
    const blocked = { id: 10, author: { id: 7 }, text: "hidden", reply_to: null }
    const reply = { id: 11, author: { id: 8 }, text: "visible", reply_to: { id: 10, author_id: 7, author_name: "Blocked", text: "hidden quote" } }
    const other = { id: 12, author: { id: 9 }, text: "also visible", reply_to: null }
    const source = [blocked, reply, other]
    const visible = filterBlockedCommunityMessages(source, [7])
    assert.deepEqual(visible.map(message => message.id), [11, 12])
    assert.equal(visible[0].reply_to, null)
    assert.equal(visible[1], other)
    assert.equal(reply.reply_to.text, "hidden quote") // Never corrupt the source cache.
    assert.deepEqual(filterBlockedCommunityMessages(source, []), source)
})
