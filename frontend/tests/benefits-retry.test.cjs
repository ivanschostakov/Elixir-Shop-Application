const assert = require("node:assert/strict")
const test = require("node:test")
const load = require("./load-ts.cjs")

test("temporary benefits failures are retried, validation errors and account changes are not", async () => {
    class ApiError extends Error { constructor(status) { super(String(status)); this.status = status } }
    let revision = 1, attempts = 0, status = 503
    const { checkMyBenefitsWithRetry } = load("services/api/benefits.ts", {
        "@/services/api/constants": { ENDPOINTS: { USERS: "/users" } },
        "@/services/commerce-account": { commerceAccountRevision: () => revision },
        "@/services/api/client": { ApiError, apiPost: async () => { attempts++; if (attempts < 3) throw new ApiError(status); return { cash_total: "12880.00" } } },
    })
    assert.equal((await checkMyBenefitsWithRetry({ use_basket: true })).cash_total, "12880.00")
    assert.equal(attempts, 3)
    attempts = 0; status = 409
    await assert.rejects(checkMyBenefitsWithRetry({ use_basket: true }), error => error.status === 409)
    assert.equal(attempts, 1)
    attempts = 0; status = 503
    const pending = checkMyBenefitsWithRetry({ use_basket: true }); revision++
    await assert.rejects(pending)
    assert.equal(attempts, 1)
})
