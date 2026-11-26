import { StyleSheet } from "react-native"
import { useLanguage } from "@/providers/language-provider"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { createCommunityChatStyles } from "@/screens/chat/community-chat-screen.styles"
import { AppSegmentedControl, type SegmentStyles } from "@/components/platform/app-segmented-control"
import type { ThemePalette } from "@/theme/colors"
import type { ChatMode } from "@/screens/chat/chat-mode-policy"
export type { ChatMode } from "@/screens/chat/chat-mode-policy"

export function ChatModeSwitcher({ mode, solidStyle = false, nativeDark, mentorStyle = false, onChange, supportUnreadCount = 0, unreadCount }: {
    mode: ChatMode; solidStyle?: boolean; nativeDark?: boolean; mentorStyle?: boolean
    onChange: (mode: ChatMode) => void; supportUnreadCount?: number; unreadCount: number
}) {
    const styles = useThemeStyles<SegmentStyles>(mentorStyle ? createMentorSwitcherStyles : createCommunityChatStyles)
    const { t } = useLanguage()
    return <AppSegmentedControl value={mode} onChange={onChange} nativeDark={nativeDark} solid={solidStyle}
        inset={mentorStyle ? 4 : 3} styles={styles}
        widthShares={mentorStyle ? width => width < 300 ? [0.20, 0.48, 0.32] : [0.30, 0.40, 0.30] : undefined}
        options={[{ value: "ai", label: t("chat.modeAi") }, { value: "community", label: t("chat.modeGroup"), badge: unreadCount }, { value: "support", label: t("chat.modeSupport"), badge: supportUnreadCount }]} />
}

function createMentorSwitcherStyles(colors: ThemePalette) {
    const base = createCommunityChatStyles(colors)
    const control = StyleSheet.create({
        nativeControl: { flex: 1, minWidth: 0, height: 44 },
        modeSwitcher: { ...base.modeSwitcher, backgroundColor: colors.surface + "CE", shadowOpacity: 0, elevation: 0 },
        modeIndicator: { ...base.modeIndicator, backgroundColor: colors.borderSoft },
        modeButton: { ...base.modeButton, paddingHorizontal: 4 },
        modeText: { ...base.modeText, fontSize: 14, lineHeight: 18, fontWeight: "600", color: colors.text },
        modeTextActive: { color: colors.text, fontWeight: "700" },
    })
    return { ...base, ...control }
}
