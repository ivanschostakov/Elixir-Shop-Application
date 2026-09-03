import { AppState, Platform } from "react-native"
import { deviceCompanionTimezone } from "@/screens/chat/companion-timezones"
import { syncCompanionTimezone } from "@/services/api/companion"

// Per authenticated account, including while chat is closed. Retry offline
// failures; do not cache success across accounts or prompt for a timezone.
export function startCompanionTimezoneSync() {
    if (Platform.OS === "web") return () => undefined
    let stopped = false, running = false, lastSynced = ""
    const sync = async (force = false) => {
        if (stopped || running || AppState.currentState !== "active") return
        const zone = deviceCompanionTimezone()
        if (!force && zone === lastSynced) return
        running = true
        try {
            await syncCompanionTimezone()
            if (!stopped) lastSynced = zone
        } catch { /* Retry on the next foreground/tick; never ask the user. */ }
        finally { running = false }
    }
    void sync(true)
    const listener = AppState.addEventListener("change", state => { if (state === "active") void sync(true) })
    const timer = setInterval(() => void sync(), 30_000)
    return () => { stopped = true; listener.remove(); clearInterval(timer) }
}
