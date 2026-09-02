const fs = require("node:fs")
const path = require("node:path")
const ts = require("typescript")

module.exports = function loadTs(relativePath, mocks = {}) {
    const filename = path.join(path.dirname(require.resolve("../package.json")), relativePath)
    const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
        fileName: filename,
    }).outputText
    const module = { exports: {} }
    const localRequire = (name) => Object.hasOwn(mocks, name) ? mocks[name] : require(name)
    new Function("require", "module", "exports", compiled)(localRequire, module, module.exports)
    return module.exports
}
