const fs = require("fs")
const path = require("path")
const { AndroidConfig, createRunOncePlugin, withAndroidManifest, withAppDelegate } = require("expo/config-plugins")

const PLUGIN_NAME = "with-yandex-mapkit"

function getMapKitApiKey() {
    return process.env.YANDEX_MAPKIT_API_KEY || process.env.EXPO_PUBLIC_YANDEX_MAPKIT_API_KEY
}

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

function ensureLocalEnvLoaded() {
    if (getMapKitApiKey()) {
        return
    }

    for (const fileName of [".env.local", ".env"]) {
        loadEnvFile(path.join(process.cwd(), fileName))

        if (getMapKitApiKey()) {
            return
        }
    }
}

function escapeSwiftString(value) {
    return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"')
}

function withYandexMapKit(config) {
    ensureLocalEnvLoaded()

    const apiKey = getMapKitApiKey()

    if (!apiKey) {
        throw new Error(
            "Missing YANDEX_MAPKIT_API_KEY (or EXPO_PUBLIC_YANDEX_MAPKIT_API_KEY) for Yandex MapKit. Set it in your shell, local .env file, or EAS environment.",
        )
    }

    const withIos = withAppDelegate(config, (config) => {
        const appDelegate = config.modResults

        if (appDelegate.language !== "swift") {
            throw new Error(`${PLUGIN_NAME} currently supports only Swift AppDelegate files.`)
        }

        if (!appDelegate.contents.includes("import YandexMapsMobile")) {
            appDelegate.contents = appDelegate.contents.replace(
                "import ReactAppDependencyProvider",
                'import ReactAppDependencyProvider\nimport YandexMapsMobile',
            )
        }

        if (!appDelegate.contents.includes("private var yandexMapKit: YMKMapKit?")) {
            appDelegate.contents = appDelegate.contents.replace(
                "  var reactNativeFactory: RCTReactNativeFactory?",
                "  var reactNativeFactory: RCTReactNativeFactory?\n  private var yandexMapKit: YMKMapKit?",
            )
        }

        const legacyInitBlock = [
            `    YMKMapKit.setApiKey("${escapeSwiftString(apiKey)}")`,
            "    let mapKit = YMKMapKit.sharedInstance()",
            "    mapKit.onStart()",
            "",
        ].join("\n")

        if (appDelegate.contents.includes(legacyInitBlock)) {
            appDelegate.contents = appDelegate.contents.replace(legacyInitBlock, "")
        }

        const launchInitBlock = [
            `    YMKMapKit.setApiKey("${escapeSwiftString(apiKey)}")`,
            "    yandexMapKit = YMKMapKit.sharedInstance()",
            "",
        ].join("\n")

        if (!appDelegate.contents.includes("yandexMapKit = YMKMapKit.sharedInstance()")) {
            appDelegate.contents = appDelegate.contents.replace(
                "    bindReactNativeFactory(factory)\n",
                `    bindReactNativeFactory(factory)\n\n${launchInitBlock}`,
            )
        }

        const lifecycleBlock = [
            "  public override func applicationDidBecomeActive(_ application: UIApplication) {",
            "    super.applicationDidBecomeActive(application)",
            "    yandexMapKit?.onStart()",
            "  }",
            "",
            "  public override func applicationDidEnterBackground(_ application: UIApplication) {",
            "    yandexMapKit?.onStop()",
            "    super.applicationDidEnterBackground(application)",
            "  }",
            "",
        ].join("\n")

        if (!appDelegate.contents.includes("applicationDidBecomeActive")) {
            appDelegate.contents = appDelegate.contents.replace(
                "  // Linking API\n",
                `${lifecycleBlock}  // Linking API\n`,
            )
        }

        return config
    })

    return withAndroidManifest(withIos, (config) => {
        const androidManifest = config.modResults
        const mainApplication = AndroidConfig.Manifest.getMainApplicationOrThrow(androidManifest)
        AndroidConfig.Manifest.addMetaDataItemToMainApplication(
            mainApplication,
            "YANDEX_MAPKIT_API_KEY",
            apiKey,
        )
        config.modResults = androidManifest
        return config
    })
}

module.exports = createRunOncePlugin(withYandexMapKit, PLUGIN_NAME, "1.0.0")
