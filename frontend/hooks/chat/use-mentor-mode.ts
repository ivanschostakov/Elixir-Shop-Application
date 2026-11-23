import { useCallback, useRef, useState } from "react"

/** Presentation mode is separate from the saved mentor profile and reminders. */
export function useMentorMode(resolveProfileEnabled: () => Promise<boolean>, initiallyShown = true) {
    const [shown, setShown] = useState(initiallyShown)
    const shownRef = useRef(initiallyShown)
    const profileResolver = useRef(resolveProfileEnabled)
    profileResolver.current = resolveProfileEnabled

    const change = useCallback((next: boolean) => {
        shownRef.current = next
        setShown(next)
    }, [])
    const resolveEnabled = useCallback(async () => shownRef.current && await profileResolver.current(), [])

    return { shown, setShown: change, resolveEnabled }
}
