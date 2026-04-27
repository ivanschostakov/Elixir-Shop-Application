import { Platform } from "react-native"

const MAPKIT_API_KEY = process.env.EXPO_PUBLIC_YANDEX_MAPKIT_API_KEY?.trim()

let initializationPromise: Promise<void> | null = null

type YandexMapModule = typeof import("react-native-yamap")

let yandexMapModulePromise: Promise<YandexMapModule> | null = null

function getYandexMapModule() {
    if (!yandexMapModulePromise) {
        yandexMapModulePromise = import("react-native-yamap")
    }

    return yandexMapModulePromise
}

export function initializeYandexMapKit() {
    if (initializationPromise) {
        return initializationPromise
    }

    initializationPromise = (async () => {
        if (Platform.OS === "ios") {
            // iOS receives the MapKit key and lifecycle calls from AppDelegate.
            return
        }

        if (!MAPKIT_API_KEY) {
            throw new Error("Missing EXPO_PUBLIC_YANDEX_MAPKIT_API_KEY.")
        }

        const { YaMap } = await getYandexMapModule()
        await YaMap.init(MAPKIT_API_KEY)
        await YaMap.resetLocale()
    })().catch((error) => {
        initializationPromise = null
        throw error
    })

    return initializationPromise
}

export function warmupYandexMapKit() {
    void initializeYandexMapKit().catch((error) => {
        console.error("[yandex-mapkit] Initialization failed.", error)
    })
}
