/** Use the screen's own route, including while another screen is entering. */
export function getScreenPathname(name: string, params?: object) {
    if (/^\([^/]+\)$/.test(name)) return null
    const segments = name.split("/").filter(segment => !/^\(.+\)$/.test(segment))
    if (segments.at(-1) === "index") segments.pop()
    return "/" + segments.map(segment => {
        const match = segment.match(/^\[(.+)\]$/)
        const value = match && params ? (params as Record<string, unknown>)[match[1]] : undefined
        return typeof value === "string" || typeof value === "number" ? String(value) : segment
    }).join("/")
}
