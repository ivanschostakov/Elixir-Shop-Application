import { Platform } from "react-native"

const MAPKIT_API_KEY_FALLBACK = process.env.EXPO_PUBLIC_YANDEX_MAPKIT_API_KEY?.trim() ?? ""

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

        const { YaMap } = await getYandexMapModule()
        // Prefer native key injection (manifest), but keep public env fallback for compatibility.
        await YaMap.init(MAPKIT_API_KEY_FALLBACK)
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
