import { requireOptionalNativeModule } from "expo"
import { useEffect, useRef, useState, type PropsWithChildren } from "react"
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"

type Updates = typeof import("expo-updates")
const updates: Updates | null = !__DEV__ && requireOptionalNativeModule<{ isEnabled: boolean }>("ExpoUpdates")?.isEnabled
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- Older local builds may have no native updater.
    ? require("expo-updates") : null

export function PlayUpdateGate({ children }: PropsWithChildren) {
    return updates ? <StartupUpdate client={updates}>{children}</StartupUpdate> : <>{children}</>
}

function StartupUpdate({ children, client }: PropsWithChildren<{ client: Updates }>) {
    // Build 6 checks and downloads on every cold start. Observe that request instead of starting a second one.
    const state = client.useUpdates()
    const [entered, setEntered] = useState(false)
    const reloadStarted = useRef(false)
    const { t } = useLanguage()
    const { palette } = useTheme()
    const running = state.currentlyRunning
    const downloaded = state.downloadedUpdate
    const pending = state.isUpdatePending && !!downloaded && (downloaded.type === "rollback"
        ? !running.isEmbeddedLaunch : downloaded.updateId !== running.updateId)
    const failed = Boolean(state.checkError || state.downloadError || running.isEmergencyLaunch)
    const checking = state.isChecking || state.isStartupProcedureRunning

    useEffect(() => {
        if (entered) return
        if (failed || state.restartCount > 0) {
            setEntered(true)
        } else if (pending) {
            if (!reloadStarted.current) {
                reloadStarted.current = true
                void client.reloadAsync().catch(() => setEntered(true))
            }
        } else if (!state.isDownloading && !checking) {
            setEntered(true)
        } else if (!state.isDownloading) {
            // A slow check must not block the shop or interrupt it after the user has entered.
            const timeout = setTimeout(() => setEntered(true), 2500)
            return () => clearTimeout(timeout)
        }
    }, [entered, failed, pending, checking, state.isDownloading, state.restartCount, client])

    if (entered) return <>{children}</>
    const progress = state.downloadProgress
    const percent = state.isDownloading && typeof progress === "number" && Number.isFinite(progress) && progress > 0
        ? Math.min(100, Math.round(progress * 100)) : null
    const title = pending ? t("ota.applying") : state.isDownloading ? t("ota.downloading") : t("ota.checking")
    return <View style={[styles.screen, { backgroundColor: palette.pageBackground }]}>
        <Text style={[styles.brand, { color: palette.stateText }]}>{t("app.name")}</Text>
        <Text accessibilityRole="header" accessibilityLiveRegion="polite" style={[styles.title, { color: palette.text }]}>{title}</Text>
        {percent === null ? <ActivityIndicator size="large" color={palette.primary} /> :
            <View accessible accessibilityRole="progressbar" accessibilityLabel={title} accessibilityValue={{ min: 0, max: 100, now: percent }} style={styles.progress}>
                <View style={[styles.track, { backgroundColor: palette.border }]}>
                    <View style={[styles.fill, { width: `${percent}%`, backgroundColor: palette.primary }]} />
                </View>
                <Text style={[styles.percent, { color: palette.text }]}>{percent}%</Text>
            </View>}
        {!pending && <Pressable accessibilityRole="button" onPress={() => setEntered(true)} style={styles.button}>
            <Text style={{ color: palette.primary }}>{t("ota.continue")}</Text>
        </Pressable>}
    </View>
}

const styles = StyleSheet.create({
    screen: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, gap: 20 },
    brand: { fontSize: 16, fontWeight: "600" },
    title: { fontSize: 24, fontWeight: "700", textAlign: "center" },
    progress: { width: "100%", maxWidth: 300, gap: 8 },
    track: { height: 6, borderRadius: 3, overflow: "hidden" },
    fill: { height: "100%" },
    percent: { textAlign: "center", fontVariant: ["tabular-nums"] },
    button: { minHeight: 44, justifyContent: "center", paddingHorizontal: 16 },
})
