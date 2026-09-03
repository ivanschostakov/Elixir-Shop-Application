// Device metadata, never a user preference. Do not infer cities/DST from offsets.
const pad = (value: number) => String(value).padStart(2, "0")

export function normalizeCompanionTimezone(value: string | null | undefined): string | null {
    let zone = value?.trim()
    if (!zone) return null
    if (/^(UTC|GMT|Z)$/i.test(zone)) return "UTC"
    if (/^(МСК|MSK|Москва|Moscow)$/i.test(zone)) zone = "Europe/Moscow"
    const offset = /^(?:UTC|GMT)?([+-])(\d{1,2})(?::?(\d{2}))?$/i.exec(zone)
    if (offset) {
        const hours = Number(offset[2]), minutes = Number(offset[3] ?? 0)
        if (hours > 14 || minutes > 59 || hours === 14 && minutes !== 0) return null
        if (!minutes) return hours ? `Etc/GMT${offset[1] === "+" ? "-" : "+"}${hours}` : "UTC"
        return `UTC${offset[1]}${pad(hours)}:${pad(minutes)}`
    }
    try { new Intl.DateTimeFormat("en", { timeZone: zone }).format(0); return zone }
    catch { return null }
}

export function deviceCompanionTimezone(): string {
    try {
        const zone = normalizeCompanionTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone)
        if (zone) return zone
    } catch { /* Fall back to the phone's exact offset, never a default city. */ }
    const offset = -new Date().getTimezoneOffset()
    return normalizeCompanionTimezone(`UTC${offset < 0 ? "-" : "+"}${pad(Math.floor(Math.abs(offset) / 60))}:${pad(Math.abs(offset) % 60)}`)!
}

export function localDateTime(value: string | Date): string {
    const date = typeof value === "string" ? new Date(value) : value
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function localEntryTimestamp(value: string, original: string): string {
    // Keep seconds and the exact occurrence of an ambiguous autumn hour unless edited.
    if (value === localDateTime(original)) return original
    const match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})$/.exec(value.trim())
    if (!match) throw new Error("Укажите дату и время в формате ГГГГ-ММ-ДД ЧЧ:ММ")
    const [, y, m, d, h, minute] = match.map(Number)
    const date = new Date(y, m - 1, d, h, minute)
    if (date.getFullYear() !== y || date.getMonth() !== m - 1 || date.getDate() !== d || date.getHours() !== h || date.getMinutes() !== minute) {
        throw new Error("Такой даты или времени нет на телефоне. Проверьте введённое время.")
    }
    return date.toISOString()
}

export function calendarDate(days = 0): string {
    const date = new Date()
    date.setDate(date.getDate() + days)
    return localDateTime(date).slice(0, 10)
}

export function deviceClockKey(): string {
    return `${deviceCompanionTimezone()}|${new Date().getTimezoneOffset()}|${calendarDate()}`
}

export function formatCompanionDate(value: string, clock: string): string {
    const zone = clock.split("|")[0]
    const fixed = /^UTC([+-])(\d{2}):(\d{2})$/.exec(zone)
    if (fixed) {
        const minutes = (Number(fixed[2]) * 60 + Number(fixed[3])) * (fixed[1] === "+" ? 1 : -1)
        return new Date(Date.parse(value) + minutes * 60_000).toLocaleString("ru-RU", { timeZone: "UTC" })
    }
    return new Date(value).toLocaleString("ru-RU", { timeZone: zone })
}
