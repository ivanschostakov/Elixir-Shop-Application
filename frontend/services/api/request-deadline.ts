export class RequestDeadlineError extends Error {}

/** Bounds headers AND body reading, even if a native fetch ignores abort(). */
export async function fetchTextWithDeadline(url: string, init: RequestInit, timeoutMs = 20000) {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let rejectAbort: (reason: Error) => void = () => undefined
    const aborted = new Promise<never>((_, reject) => { rejectAbort = reject })
    const abort = () => {
        rejectAbort(new RequestDeadlineError("Request interrupted or timed out"))
        controller.abort()
    }
    init.signal?.addEventListener("abort", abort)
    if (timeoutMs > 0) timer = setTimeout(abort, timeoutMs)
    const operation = async () => {
        if (init.signal?.aborted) throw new RequestDeadlineError("Request interrupted")
        const response = await fetch(url, { ...init, signal: controller.signal })
        const text = response.status === 204 ? "" : await response.text()
        return { response, text }
    }
    try {
        return await Promise.race([operation(), aborted])
    } finally {
        clearTimeout(timer)
        init.signal?.removeEventListener("abort", abort)
    }
}
