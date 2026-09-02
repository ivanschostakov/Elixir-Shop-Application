const { test } = require("node:test")
const assert = require("node:assert/strict")
const loadTs = require("./load-ts.cjs")

for (const platform of ["ios", "android", "web"]) {
    test(`backend flag controls ${platform} without account-specific logic`, () => {
        const features = loadTs("services/app-features.ts", { "react-native": { Platform: { OS: platform } }, react: {} })
        assert.equal(features.isCatalogAvailable(), platform !== "ios")
        features.applyAppFeaturePolicy(false)
        assert.equal(features.isCatalogAvailable(), true)
        features.applyAppFeaturePolicy(true)
        assert.equal(features.isCatalogAvailable(), platform !== "ios")
        features.applyAppFeaturePolicy(undefined)
        assert.equal(features.isCatalogAvailable(), platform !== "ios")
        for (const route of ["/products/1", "/basket?draftId=1", "/discover/", "/checkout", "/favorites"]) {
            assert.equal(features.isCatalogRoute(route), true)
        }
        for (const route of ["/", "/profile", "/chat", "/delivery", "/profile-history", "/product-settings"]) {
            assert.equal(features.isCatalogRoute(route), false)
        }
    })
}
