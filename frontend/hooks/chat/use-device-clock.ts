import { useEffect, useState } from "react"
import { AppState } from "react-native"
import { deviceClockKey } from "@/screens/chat/companion-timezones"

export function useDeviceClock() {
    const [clock, setClock] = useState(deviceClockKey)
    useEffect(() => {
        const update = () => { if (AppState.currentState === "active") setClock(deviceClockKey()) }
        update()
        const listener = AppState.addEventListener("change", update)
        const timer = setInterval(update, 30_000)
        return () => { listener.remove(); clearInterval(timer) }
    }, [])
    return clock
}
