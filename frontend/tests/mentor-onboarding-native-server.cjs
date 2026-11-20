/* Local-only synthetic iOS preview; never imported by application routes.
 * node tests/mentor-onboarding-native-server.cjs
 * Open exp+elixir-shop://expo-development-client/?url=http%3A%2F%2F127.0.0.1%3A8104%3Fscreen%3Dresult
 * Screens: required, activity, result, optional, experience, conditions, reminders, home, home-empty.
 * No account or network mutations.
 */
/* global __dirname */
const path = require("node:path")
const Metro = require("metro")
const config = require("../metro.config")
const port = 8104, base = `http://127.0.0.1:${port}`
config.maxWorkers = 2
config.watchFolders = [path.resolve(__dirname, "..")]
const fixtures = new Set(["@/providers/theme-provider", "@/providers/language-provider", "@/services/api/companion", "@/services/api/companion-food", "@/services/api/ai-chat", "@/services/notifications/order-status-notifications"])
config.resolver.resolveRequest = (context, name, platform) => context.resolveRequest(context, fixtures.has(name) ? path.join(__dirname, "mentor-onboarding-native.jsx") : name.startsWith("@/") ? path.resolve(__dirname, "..", name.slice(2)) : name, platform)
config.server = { ...config.server, port, enhanceMiddleware: middleware => (req, res, next) => {
    const url = new URL(req.url, base)
    if (url.pathname === "/" || url.pathname === "/manifest") {
        const screen = ["required", "activity", "result", "optional", "experience", "conditions", "reminders", "home", "home-empty"].includes(url.searchParams.get("screen")) ? url.searchParams.get("screen") : "required"
        res.setHeader("Content-Type", "application/json")
        res.setHeader("expo-protocol-version", "0")
        res.setHeader("expo-sfv-version", "0")
        res.end(JSON.stringify({
            id: "c3ef4b95-85c9-4cdc-981b-dd618698e52e", createdAt: new Date().toISOString(), runtimeVersion: "0.1.1",
            launchAsset: { key: "mentor-onboarding-fixture", contentType: "application/javascript", url: `${base}/tests/mentor-onboarding-native.bundle?platform=ios&dev=true&minify=false&transform.engine=hermes&transform.bytecode=0&previewScreen=${screen}` },
            assets: [], metadata: {}, extra: { expoClient: { name: "Mentor Onboarding Preview", slug: "elixir-shop", scheme: "elixirpeptide", sdkVersion: "54.0.0", version: "0.1.1", hostUri: `127.0.0.1:${port}` }, expoGo: { debuggerHost: `127.0.0.1:${port}`, developer: { tool: "expo-cli" }, packagerOpts: { dev: true } } },
        }))
        return
    }
    middleware(req, res, next)
} }
Metro.runServer(config, { host: "127.0.0.1", port }).then(() => console.log(`Native mentor preview ready: ${base}`)).catch(error => { console.error(error); process.exitCode = 1 })
