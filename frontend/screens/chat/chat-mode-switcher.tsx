import { StyleSheet } from "react-native"
import { useLanguage } from "@/providers/language-provider"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { createCommunityChatStyles } from "@/screens/chat/community-chat-screen.styles"
import { AppSegmentedControl } from "@/components/platform/app-segmented-control"
import type { ChatMode } from "@/screens/chat/chat-mode-policy"
export type { ChatMode } from "@/screens/chat/chat-mode-policy"

export function ChatModeSwitcher({ mode, solidStyle = false, nativeDark, mentorStyle = false, onChange, supportUnreadCount = 0, unreadCount }: {
    mode: ChatMode; solidStyle?: boolean; nativeDark?: boolean; mentorStyle?: boolean
    onChange: (mode: ChatMode) => void; supportUnreadCount?: number; unreadCount: number
}) {
    const theme = useThemeStyles(createCommunityChatStyles), { t } = useLanguage()
    return <AppSegmentedControl value={mode} onChange={onChange} nativeDark={nativeDark} solid={solidStyle} compactLabels={mentorStyle}
        inset={mentorStyle ? 4 : 3} styles={mentorStyle ? { ...theme, ...mentorSwitcherStyles } : theme}
        widthShares={mentorStyle ? width => width < 300 ? [0.20, 0.48, 0.32] : [0.30, 0.40, 0.30] : undefined}
        options={[{ value: "ai", label: t("chat.modeAi") }, { value: "community", label: t("chat.modeGroup"), badge: unreadCount }, { value: "support", label: t("chat.modeSupport"), badge: supportUnreadCount }]} />
}

const mentorSwitcherStyles = StyleSheet.create({
    nativeControl: { flex: 1, minWidth: 0, height: 44 },
    modeSwitcher: { flex: 1, minWidth: 0, height: 42, padding: 3, borderRadius: 23, flexDirection: "row", overflow: "hidden", shadowOpacity: 0, elevation: 0 },
    modeIndicator: { position: "absolute", left: 3, top: 3, height: 34, borderRadius: 19, backgroundColor: "#078AFF" },
    modeButton: { flex: 1, minWidth: 0, height: 34, paddingHorizontal: 4, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 4, zIndex: 1 },
    modeText: { flexShrink: 1, color: "#616B77", fontSize: 12, lineHeight: 16, fontWeight: "700", textAlign: "center" },
    modeTextActive: { color: "#FFFFFF" },
    modeBadge: { minWidth: 18, height: 18, paddingHorizontal: 4, borderRadius: 9, backgroundColor: "#CB1745", alignItems: "center", justifyContent: "center" },
    modeBadgeText: { color: "#FFFFFF", fontSize: 10, lineHeight: 12, fontWeight: "600" },
})
