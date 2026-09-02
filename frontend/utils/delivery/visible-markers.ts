type Marker = { point: { lat: number; lon: number } }

/** Bound native work to the current viewport, and refresh the selection on pan. */
export function selectVisibleMarkers<T extends Marker>(
    markers: T[], region: { lat: number; lon: number; zoom?: number }, limit: number,
): T[] {
    const lonSpan = Math.min(180, 720 / 2 ** (region.zoom ?? 8))
    const latSpan = lonSpan * 1.5
    const longitudeDistance = (lon: number) => Math.abs(((lon - region.lon + 540) % 360) - 180)
    const scale = Math.max(0.1, Math.cos(region.lat * Math.PI / 180))
    const candidates = markers
        .filter(({ point }) => Number.isFinite(point.lat) && Number.isFinite(point.lon)
            && Math.abs(point.lat - region.lat) <= latSpan && longitudeDistance(point.lon) <= lonSpan)
        .map((marker) => ({ marker, distance: (marker.point.lat - region.lat) ** 2
            + (longitudeDistance(marker.point.lon) * scale) ** 2 }))
        .sort((a, b) => a.distance - b.distance)
        .map(({ marker }) => marker)
    if (candidates.length <= limit) return candidates
    // Keep a representative point in each cell before filling by proximity.
    // Otherwise a zoomed-out country view would show only its central cities.
    const divisions = Math.max(1, Math.floor(Math.sqrt(limit)))
    const cells = new Map<string, T>()
    for (const marker of candidates) {
        const dx = ((marker.point.lon - region.lon + 540) % 360) - 180
        const x = Math.min(divisions - 1, Math.floor((dx + lonSpan) / (2 * lonSpan) * divisions))
        const y = Math.min(divisions - 1, Math.floor((marker.point.lat - region.lat + latSpan) / (2 * latSpan) * divisions))
        const key = `${x}:${y}`
        if (!cells.has(key)) cells.set(key, marker)
    }
    const selected = new Set(cells.values())
    for (const marker of candidates) {
        if (selected.size >= limit) break
        selected.add(marker)
    }
    return Array.from(selected).slice(0, limit)
}
