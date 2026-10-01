const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

function harness() {
    const slots = [], effects = []
    let cursor = 0
    const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]))
    const react = {
        useState(initial) {
            const i = cursor++
            if (!(i in slots)) slots[i] = typeof initial === "function" ? initial() : initial
            return [slots[i], value => { slots[i] = typeof value === "function" ? value(slots[i]) : value }]
        },
        useRef(initial) { const i = cursor++; if (!(i in slots)) slots[i] = { current: initial }; return slots[i] },
        useCallback(callback, deps) { const i = cursor++; if (!same(slots[i]?.deps, deps)) slots[i] = { deps, callback }; return slots[i].callback },
        useEffect(callback, deps) {
            const i = cursor++
            if (!same(slots[i]?.deps, deps)) effects.push(() => { slots[i]?.cleanup?.(); slots[i] = { deps, cleanup: callback() } })
        },
    }
    const { useAsyncData } = loadTs("hooks/shared/use-async-data.ts", {
        react, "@/utils/errors": { getErrorMessage: error => error.message, showBackendErrorAlert: () => {} },
    })
    return {
        render: function Render(options) { cursor = 0; const result = useAsyncData(options); effects.splice(0).forEach(run => run()); return result },
        unmount() { slots.forEach(slot => slot?.cleanup?.()) },
    }
}
const pending = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const flush = () => new Promise(resolve => setImmediate(resolve))

test("refresh retains content without a new page loader, including failed refreshes", async () => {
    const hook = harness(), first = pending(), second = pending()
    let request = first
    const options = { deps: [7], initialData: null, resetOnLoad: true, fetcher: () => request.promise }
    assert.equal(hook.render(options).loading, true)
    first.resolve({ name: "Loaded product" }); await flush()
    let result = hook.render(options)
    assert.equal(result.loading, false)
    request = second
    const refresh = result.reload()
    result = hook.render(options)
    assert.deepEqual(result.data, { name: "Loaded product" })
    assert.equal(result.loading, false)
    second.reject(new Error("offline")); await refresh
    result = hook.render(options)
    assert.deepEqual(result.data, { name: "Loaded product" })
    assert.equal(result.error, "offline")
    assert.equal(result.loading, false)
    hook.unmount()
})

test("a customer/resource change hides previous content immediately and ignores late responses", async () => {
    const hook = harness(), first = pending(), second = pending(), stale = pending()
    let request = first
    const firstOptions = { deps: [7, "product-a"], initialData: null, fetcher: () => request.promise }
    hook.render(firstOptions)
    first.resolve({ owner: 7 }); await flush()
    const result = hook.render(firstOptions)
    request = stale
    const oldReload = result.reload()
    const secondOptions = { deps: [8, "product-b"], initialData: null, fetcher: () => second.promise }
    assert.equal(hook.render(secondOptions).data, null)
    assert.equal(hook.render(secondOptions).loading, true)
    assert.equal(await result.reload(), null, "A retained callback cannot cancel the new customer's request")
    result.setData({ owner: 7, stale: true })
    assert.equal(hook.render(secondOptions).data, null, "A retained setter cannot write another customer's content")
    stale.resolve({ owner: 7, stale: true }); await oldReload
    assert.equal(hook.render(secondOptions).data, null)
    second.resolve({ owner: 8 }); await flush()
    assert.deepEqual(hook.render(secondOptions).data, { owner: 8 })
    hook.unmount()
})

test("an older overlapping request cannot replace a newer successful reload", async () => {
    const hook = harness(), old = pending(), next = pending()
    let request = old
    const options = { deps: [], enabled: false, initialData: null, fetcher: () => request.promise }
    const result = hook.render(options)
    const oldReload = result.reload()
    request = next
    const nextReload = result.reload()
    next.resolve("current"); await nextReload
    assert.equal(hook.render(options).data, "current")
    old.resolve("stale"); await oldReload
    assert.equal(hook.render(options).data, "current")
    hook.unmount()
})

test("explicit error clearing and unmounting reject stale content", async () => {
    const hook = harness(), first = pending(), failed = pending(), late = pending()
    let request = first
    const options = { deps: [], initialData: [], preserveDataOnError: false, fetcher: () => request.promise }
    hook.render(options); first.resolve(["data"]); await flush()
    let result = hook.render(options)
    request = failed
    const reload = result.reload(); failed.reject(new Error("removed")); await reload
    assert.deepEqual(hook.render(options).data, [])
    request = late
    result = hook.render(options)
    const cancelled = result.reload(); hook.unmount()
    late.resolve(["late"]); await cancelled
    assert.deepEqual(hook.render(options).data, [])
})
