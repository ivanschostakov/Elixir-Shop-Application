export const DEFAULT_COMPANION_TIMEZONE = "Europe/Moscow"

const cityNames: Record<string, string> = {
    "Europe/Kaliningrad": "Калининград",
    "Europe/Moscow": "Москва, Санкт-Петербург",
    "Europe/Samara": "Самара",
    "Asia/Yekaterinburg": "Екатеринбург, Уфа",
    "Asia/Omsk": "Омск",
    "Asia/Krasnoyarsk": "Красноярск",
    "Asia/Irkutsk": "Иркутск",
    "Asia/Yakutsk": "Якутск",
    "Asia/Vladivostok": "Владивосток",
    "Asia/Magadan": "Магадан",
    "Asia/Kamchatka": "Камчатка",
    "UTC": "Всемирное время (UTC)",
}

export function normalizeCompanionTimezone(value: string | null | undefined): string | null {
    let zone = value?.trim()
    if (!zone) return null
    if (/^(UTC|GMT|Z)$/i.test(zone)) zone = "UTC"
    else if (/^(МСК|MSK|Москва|Moscow)$/i.test(zone)) zone = DEFAULT_COMPANION_TIMEZONE
    else {
        const offset = /^(?:UTC|GMT)?([+-])(\d{1,2})(?::?00)?$/i.exec(zone)
        if (offset && Number(offset[2]) <= 14) {
            const hours = Number(offset[2])
            zone = hours ? `Etc/GMT${offset[1] === "+" ? "-" : "+"}${hours}` : "UTC"
        }
    }
    // Some Intl versions accept fractional offset strings; the server requires
    // a named zone. Do not guess a city (and its DST rules) from an offset.
    if (/^(?:(?:UTC|GMT)?[+-])/i.test(zone)) return null
    try { new Intl.DateTimeFormat("en", { timeZone: zone }).format(0); return zone }
    catch { return null }
}

export function deviceCompanionTimezone(): string | null {
    try { return normalizeCompanionTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone) }
    catch { return null }
}

export function companionTimezoneChoices(current?: string) {
    const device = deviceCompanionTimezone()
    let supported: string[] = []
    try {
        const intl = Intl as typeof Intl & { supportedValuesOf?: (key: "timeZone") => string[] }
        supported = intl.supportedValuesOf?.("timeZone") ?? []
    } catch { /* Older Hermes still gets regional, current and device choices. */ }
    const selected = normalizeCompanionTimezone(current)
    const zones = [...new Set([selected, device, ...Object.keys(cityNames), ...supported].filter((zone): zone is string => !!zone))]
    return zones.map(value => ({ value, label: `${cityNames[value] ?? value.replace(/_/g, " ")}${value === device ? " · на устройстве" : ""}` }))
}
