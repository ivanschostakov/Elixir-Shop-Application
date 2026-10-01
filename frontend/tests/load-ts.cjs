const fs = require("node:fs")
const path = require("node:path")
const ts = require("typescript")
const i18nModules = new Map()

module.exports = function loadTs(relativePath, mocks = {}) {
    const filename = path.join(path.dirname(require.resolve("../package.json")), relativePath)
    const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
        fileName: filename,
    }).outputText
    const module = { exports: {} }
    const localRequire = (name) => {
        if (Object.hasOwn(mocks, name)) return mocks[name]
        if (name.startsWith("@/i18n/")) {
            if (!i18nModules.has(name)) i18nModules.set(name, loadTs(name.slice(2) + ".ts"))
            return i18nModules.get(name)
        }
        return require(name)
    }
    new Function("require", "module", "exports", compiled)(localRequire, module, module.exports)
    return module.exports
}
