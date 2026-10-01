import { useCallback, useRef, useState } from "react"

/** Presentation mode is separate from the saved mentor profile and reminders. */
export function useMentorMode(resolveProfileEnabled: () => Promise<boolean>) {
    const [shown, setShown] = useState(true)
    const shownRef = useRef(true)
    const profileResolver = useRef(resolveProfileEnabled)
    profileResolver.current = resolveProfileEnabled

    const change = useCallback((next: boolean) => {
        shownRef.current = next
        setShown(next)
    }, [])
    const resolveEnabled = useCallback(async () => shownRef.current && await profileResolver.current(), [])

    return { shown, setShown: change, resolveEnabled }
}
