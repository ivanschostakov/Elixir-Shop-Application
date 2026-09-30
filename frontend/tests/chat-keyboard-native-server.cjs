/*
 * Local-only native verification; never loaded by app routes.
 * Run from frontend: node tests/chat-keyboard-native-server.cjs
 * Open the already installed iOS dev client with:
 *   exp+elixir-shop://expo-development-client/?url=http%3A%2F%2F127.0.0.1%3A8103
 * The 15-second fixture checks real keyboard geometry, a 12-line draft,
 * incoming messages while reading history, and a lower workout form field.
 * Measurements append to /private/tmp/elixir-native-keyboard-metrics.jsonl.
 * Reopen the URL with a unique query on its encoded localhost URL to rerun.
 */
/* global __dirname */
const path = require("node:path")
const fs = require("node:fs")
const Metro = require("metro")
const config = require("../metro.config")
const port = 8103
const base = `http://127.0.0.1:${port}`
config.maxWorkers = 2
config.watchFolders = [path.resolve(__dirname, "..")]
config.resolver.resolveRequest = (context, moduleName, platform) => context.resolveRequest(context, moduleName.startsWith("@/") ? path.resolve(__dirname, "..", moduleName.slice(2)) : moduleName, platform)
config.server = { ...config.server, port, enhanceMiddleware: middleware => (req, res, next) => {
    const pathname = new URL(req.url, base).pathname
    if (pathname === "/metrics" && req.method === "POST") {
        let body = ""
        req.on("data", part => { body += part })
        req.on("end", () => { fs.appendFileSync("/private/tmp/elixir-native-keyboard-metrics.jsonl", `${body}\n`); console.log("METRICS", body); res.end("ok") })
        return
    }
    if (pathname === "/" || pathname === "/manifest") {
        res.setHeader("Content-Type", "application/json")
        res.setHeader("expo-protocol-version", "0")
        res.setHeader("expo-sfv-version", "0")
        res.end(JSON.stringify({
            id: "ef5ac878-476b-459c-9fa2-649a49729290", createdAt: new Date().toISOString(), runtimeVersion: "0.1.1",
            launchAsset: { key: "native-keyboard-fixture", contentType: "application/javascript", url: `${base}/tests/chat-keyboard-native.bundle?platform=ios&dev=true&minify=false&transform.engine=hermes&transform.bytecode=0` },
            assets: [], metadata: {}, extra: { expoClient: { name: "Native Keyboard Fixture", slug: "elixir-shop", scheme: "elixirpeptide", sdkVersion: "54.0.0", version: "0.1.1", hostUri: `127.0.0.1:${port}` }, expoGo: { debuggerHost: `127.0.0.1:${port}`, developer: { tool: "expo-cli" }, packagerOpts: { dev: true } } },
        }))
        return
    }
    middleware(req, res, next)
} }
Metro.runServer(config, { host: "127.0.0.1", port }).then(() => console.log(`Native fixture ready: ${base}`)).catch(error => { console.error(error); process.exitCode = 1 })
