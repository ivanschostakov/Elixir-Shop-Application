/* global __dirname */
// Builds only the offline fixture bundle, never an IPA or production entry point.
const path = require("node:path")
const Metro = require("metro")
const config = require("../metro.config")
const fixture = path.join(__dirname, "mentor-wellbeing-native.jsx")
const mocks = new Set(["@/providers/theme-provider", "@/providers/language-provider", "@/services/api/companion", "@/utils/errors"])
config.maxWorkers = 2
config.watchFolders = [path.resolve(__dirname, "..")]
config.resolver.useWatchman = false
config.resolver.resolveRequest = (context, name, platform) => context.resolveRequest(context, mocks.has(name) ? fixture : name.startsWith("@/") ? path.resolve(__dirname, "..", name.slice(2)) : name, platform)
Metro.runBuild(config, { entry: fixture, platform: "ios", dev: false, minify: false, bundleOut: "/private/tmp/elixir-wellbeing-preview.bundle" }).catch(error => { console.error(error); process.exitCode = 1 })
