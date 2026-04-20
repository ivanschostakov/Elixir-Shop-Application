import { Platform } from "react-native"
import { Geocoder, YaMap } from "react-native-yamap"

const MAPKIT_API_KEY = process.env.EXPO_PUBLIC_YANDEX_MAPKIT_API_KEY?.trim()
const GEOCODER_API_KEY = process.env.EXPO_PUBLIC_YANDEX_GEOCODER_API_KEY?.trim()

let geocoderInitialized = false
let initializationPromise: Promise<void> | null = null

function initializeGeocoder() {
    if (!GEOCODER_API_KEY || geocoderInitialized) {
        return
    }

    Geocoder.init(GEOCODER_API_KEY)
    geocoderInitialized = true
}

export function initializeYandexMapKit() {
    if (initializationPromise) {
        return initializationPromise
    }

    initializationPromise = (async () => {
        if (!MAPKIT_API_KEY) {
            throw new Error("Missing EXPO_PUBLIC_YANDEX_MAPKIT_API_KEY.")
        }

        // iOS receives the MapKit key from the Expo config plugin in AppDelegate.
        if (Platform.OS === "android") {
            await YaMap.init(MAPKIT_API_KEY)
            await YaMap.resetLocale()
        } else {
            // iOS locale must be set before the first map render.
            await YaMap.resetLocale()
        }

        initializeGeocoder()
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
