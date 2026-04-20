import { Platform } from "react-native"

type YandexMapKitModule = typeof import("@/services/maps/yandex-mapkit.native")

let yandexMapKitModulePromise: Promise<YandexMapKitModule> | null = null

function getYandexMapKitModule() {
    if (yandexMapKitModulePromise) {
        return yandexMapKitModulePromise
    }

    if (Platform.OS === "web") {
        yandexMapKitModulePromise = import("./yandex-mapkit.web") as Promise<YandexMapKitModule>
        return yandexMapKitModulePromise
    }

    yandexMapKitModulePromise = import("./yandex-mapkit.native") as Promise<YandexMapKitModule>
    return yandexMapKitModulePromise
}

export async function initializeYandexMapKit() {
    const yandexMapKitModule = await getYandexMapKitModule()
    return yandexMapKitModule.initializeYandexMapKit()
}

export function warmupYandexMapKit() {
    void getYandexMapKitModule().then((yandexMapKitModule) => {
        yandexMapKitModule.warmupYandexMapKit()
    })
}
