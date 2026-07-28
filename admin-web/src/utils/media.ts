const ADMIN_MEDIA_PATH_PREFIX = "/media/"

/**
 * Public media is proxied through the admin origin. Product payloads can still
 * contain the public API origin, which is rejected by the admin CSP (`img-src
 * 'self'`). Keep the path and cache-busting query while serving it same-origin.
 */
export function resolveAdminMediaUrl(value: string | null | undefined) {
  const trimmedValue = value?.trim()
  if (!trimmedValue) return undefined

  try {
    const url = new URL(trimmedValue, window.location.origin)
    if (url.pathname.startsWith(ADMIN_MEDIA_PATH_PREFIX)) {
      return `${url.pathname}${url.search}${url.hash}`
    }
  } catch {
    return trimmedValue
  }

  return trimmedValue
}
