const path = require("path")

const { getDefaultConfig } = require("expo/metro-config")

const projectRoot = __dirname
const config = getDefaultConfig(projectRoot)

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
