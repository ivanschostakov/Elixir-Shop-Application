const path = require("path")

const { getDefaultConfig } = require("expo/metro-config")

const projectRoot = __dirname
if ((process.env.ELIXIR_PLAY_OTA === "1" || process.env.ELIXIR_ANDROID_STORE === "1") && !process.env.EXPO_PUBLIC_API_BASE_URL?.trim()) {
    throw new Error("Set EXPO_PUBLIC_API_BASE_URL in the EAS production environment before exporting the Play update.")
}
const config = getDefaultConfig(projectRoot)
// Build 6 predates several native Android controls. Its OTA export resolves
// component.android.play.tsx before the implementation used in new builds.
if (process.env.ELIXIR_PLAY_OTA === "1") {
    config.resolver.sourceExts.unshift("play.tsx")
}

function escapeRegExp(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function blockListPattern(relativePath) {
    const absolutePath = path.resolve(projectRoot, relativePath)
    return new RegExp(`^${escapeRegExp(absolutePath)}(?:\\/.*)?$`)
}
config.transformer.babelTransformerPath = require.resolve("react-native-svg-transformer/expo")
config.resolver.assetExts = config.resolver.assetExts.filter((ext) => ext !== "svg")
config.resolver.sourceExts.push("svg")

const blockedPaths = [
    ".expo",
    ".idea",
    "android/app/build",
    "dist",
    "expo-env.d.ts",
    "ios/build",
]

const existingBlockList = Array.isArray(config.resolver.blockList)
    ? config.resolver.blockList
    : config.resolver.blockList
      ? [config.resolver.blockList]
      : []

config.resolver.blockList = [
    ...existingBlockList,
    ...blockedPaths.map(blockListPattern),
]

module.exports = config
