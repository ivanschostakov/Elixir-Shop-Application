const fs = require("fs")
const path = require("path")

const appJson = require("./app.json")
const projectRoot = path.dirname(require.resolve("./app.json"))

const REQUIRED_EAS_ENV_KEYS = [
    "EXPO_PUBLIC_API_BASE_URL",
    "EXPO_PUBLIC_APP_JS_VERSION",
]
const REQUIRED_ANDROID_EAS_ENV_KEYS = [
    "EXPO_PUBLIC_PLAY_INTEGRITY_CLOUD_PROJECT_NUMBER",
]

function stripWrappingQuotes(value) {
    if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
    ) {
        return value.slice(1, -1)
    }

    return value
}

function loadEnvFile(filePath) {
    if (!fs.existsSync(filePath)) {
        return
    }

    const contents = fs.readFileSync(filePath, "utf8")

    for (const line of contents.split(/\r?\n/)) {
        const trimmedLine = line.trim()

        if (!trimmedLine || trimmedLine.startsWith("#")) {
            continue
        }

        const assignment = trimmedLine.startsWith("export ")
            ? trimmedLine.slice("export ".length)
            : trimmedLine
        const separatorIndex = assignment.indexOf("=")

        if (separatorIndex === -1) {
            continue
        }

        const key = assignment.slice(0, separatorIndex).trim()

        if (!key || process.env[key]) {
            continue
        }

        const rawValue = assignment.slice(separatorIndex + 1).trim()
        process.env[key] = stripWrappingQuotes(rawValue)
    }
}

function loadLocalEnv() {
    for (const fileName of [".env.local", ".env"]) {
        loadEnvFile(path.join(projectRoot, fileName))
    }
}

function getEnvValue(key) {
    return process.env[key]?.trim() || undefined
}

function shouldRequireEasEnv() {
    return Boolean(process.env.EAS_BUILD || process.env.EAS_BUILD_PROFILE || process.env.EAS_LOCAL_BUILD)
}

function shouldRequireAndroidEasEnv() {
    return process.env.EAS_BUILD_PLATFORM === "android" || process.env.EAS_BUILD_PLATFORM === "all"
}

function validateRequiredEnv() {
    if (!shouldRequireEasEnv()) {
        return
    }

    const requiredKeys = shouldRequireAndroidEasEnv()
        ? [...REQUIRED_EAS_ENV_KEYS, ...REQUIRED_ANDROID_EAS_ENV_KEYS]
        : REQUIRED_EAS_ENV_KEYS
    const missingKeys = requiredKeys.filter((key) => !getEnvValue(key))
    if (missingKeys.length === 0) {
        return
    }

    const profile = process.env.EAS_BUILD_PROFILE || "unknown"
    throw new Error(
        `[app.config] Missing required Expo environment variable(s) for EAS profile "${profile}": ${missingKeys.join(", ")}`,
    )
}

function compactObject(value) {
    return Object.fromEntries(
        Object.entries(value).filter(([, entryValue]) => entryValue !== undefined),
    )
}

module.exports = () => {
    loadLocalEnv()
    validateRequiredEnv()

    const apiBaseUrl = getEnvValue("EXPO_PUBLIC_API_BASE_URL")
    const appJsVersion = getEnvValue("EXPO_PUBLIC_APP_JS_VERSION")
    const androidCloudProjectNumber = getEnvValue("EXPO_PUBLIC_PLAY_INTEGRITY_CLOUD_PROJECT_NUMBER")
    const appIntegrityDevToken = getEnvValue("EXPO_PUBLIC_APP_INTEGRITY_DEV_TOKEN")
    const baseConfig = appJson.expo
    const baseExtra = baseConfig.extra ?? {}
    const baseAppIntegrity = baseExtra.appIntegrity ?? {}

    return {
        expo: {
            ...baseConfig,
            extra: compactObject({
                ...baseExtra,
                apiBaseUrl,
                appJsVersion,
                appIntegrity: compactObject({
                    ...baseAppIntegrity,
                    androidCloudProjectNumber,
                    devToken: appIntegrityDevToken,
                }),
            }),
        },
    }
}
