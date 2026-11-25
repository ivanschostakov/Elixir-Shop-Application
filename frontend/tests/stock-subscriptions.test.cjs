const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

test("stock alerts read, subscribe and unsubscribe through the versioned users API", async () => {
    const calls = []
    const client = Object.fromEntries(["apiGet", "apiPost", "apiDelete"].map(method => [
        method,
        async (...args) => { calls.push([method, ...args]); return { product_id: 264, is_subscribed: method !== "apiDelete" } },
    ]))
    const api = loadTs("services/api/stock-subscriptions.ts", {
        "@/services/api/client": client,
        "@/services/api/constants": { ENDPOINTS: { USERS: "/v1/users" } },
    })

    await api.getProductStockSubscriptionStatus(264)
    await api.subscribeToProductStock(264)
    await api.unsubscribeFromProductStock(264)

    const endpoint = "/v1/users/me/stock-subscriptions/products/264"
    assert.deepEqual(calls, [["apiGet", endpoint], ["apiPost", endpoint, {}], ["apiDelete", endpoint]])
})
