import { useEffect, useRef } from "react"

export type MentorQuestion = { id: string; text: string }

/** Send once after the retained chat is visible and ready; normal chat has no question. */
export function useMentorQuestion({ question, active, busy, send, handled, onError }: {
    question?: MentorQuestion | null; active: boolean; busy: boolean
    send: (text: string) => Promise<unknown>; handled?: (id: string) => void; onError: (error: unknown, text: string) => void
}) {
    const dispatched = useRef<string | null>(null)
    const latest = useRef({ send, handled, onError }); latest.current = { send, handled, onError }
    useEffect(() => {
        if (!question || !active || busy || dispatched.current === question.id) return
        // Let the editor finish dismissing before a consent alert or response appears.
        const timer = setTimeout(() => {
            dispatched.current = question.id
            const callbacks = latest.current
            callbacks.handled?.(question.id)
            void callbacks.send(question.text).catch(error => callbacks.onError(error, question.text))
        }, 180)
        return () => clearTimeout(timer)
    }, [question, active, busy])
}
