const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")
const { selectVisibleMarkers } = loadTs("utils/delivery/visible-markers.ts")
const { fetchTextWithDeadline, RequestDeadlineError } = loadTs("services/api/request-deadline.ts")

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
