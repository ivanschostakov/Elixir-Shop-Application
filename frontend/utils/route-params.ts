export type SearchParamValue = string | string[] | undefined

export function parsePositiveRouteId(value: SearchParamValue) {
    const rawValue = Array.isArray(value) ? value[0] : value
    if (!rawValue) {
        return null
    }

    const parsed = Number(rawValue)
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

export function parseDraftId(rawDraftId: SearchParamValue) {
    return parsePositiveRouteId(rawDraftId)
}

export function parseBooleanSearchParam(rawValue: SearchParamValue) {
    const value = Array.isArray(rawValue) ? rawValue[0] : rawValue
    if (!value) {
        return false
    }

    const normalized = value.toLowerCase()
    return normalized === "1" || normalized === "true" || normalized === "yes"
}
