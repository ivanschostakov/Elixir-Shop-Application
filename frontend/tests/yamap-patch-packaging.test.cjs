const assert = require("node:assert/strict")
const { spawnSync } = require("node:child_process")
const fs = require("node:fs")
const path = require("node:path")
const test = require("node:test")
const ignore = require("ignore")

test("tracked Yandex Maps patch templates are not excluded from EAS uploads", () => {
    const root = path.resolve(__dirname, "../..")
    const prefix = "frontend/scripts/react-native-yamap-patches/"
    const tracked = spawnSync("git", ["ls-files", "--", prefix], { cwd: root, encoding: "utf8" })
    assert.equal(tracked.status, 0, tracked.stderr)
    const files = tracked.stdout.trim().split("\n")
    assert.ok(files.includes(`${prefix}build/components/ClusteredYamap.js`))
    assert.ok(files.includes(`${prefix}build/components/ClusteredYamap.d.ts`))
    const rootRules = ignore().add(fs.readFileSync(path.join(root, ".gitignore"), "utf8"))
    const frontendRules = ignore().add(fs.readFileSync(path.join(root, "frontend/.gitignore"), "utf8"))
    for (const file of files) {
        assert.ok(fs.existsSync(path.join(root, file)), `Missing template: ${file}`)
        assert.equal(rootRules.ignores(file), false, `Root rules exclude template from EAS: ${file}`)
        assert.equal(frontendRules.ignores(file.slice("frontend/".length)), false, `Frontend rules exclude template: ${file}`)
    }
    // EAS applies ignore rules even to files already tracked in Git.
    const ignored = spawnSync("git", ["check-ignore", "--no-index", "--stdin"], {
        cwd: root, encoding: "utf8", input: files.join("\n") + "\n",
    })
    assert.equal(ignored.status, 1, `Patch templates excluded from upload: ${ignored.stdout}\n${ignored.stderr}`)
})
