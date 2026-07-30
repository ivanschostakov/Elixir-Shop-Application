import { StyleSheet } from "react-native"

import type { ThemePalette } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

export const createSupportChatStyles = (colors: ThemePalette) => StyleSheet.create({
    overlay: { ...StyleSheet.absoluteFillObject, zIndex: 55 },
    hidden: { display: "none" },
    screen: { flex: 1, backgroundColor: colors.surfaceSoft },
    header: { position: "absolute", left: spacing.md, right: spacing.md, zIndex: 12, flexDirection: "row", alignItems: "center", gap: spacing.sm },
    backButton: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceOverlay, borderColor: colors.borderSoft, borderWidth: 1 },
    backText: { color: colors.text, fontSize: 25, lineHeight: 27 },
    keyboard: { flex: 1 },
    messages: { flex: 1 },
    messagesContent: { flexGrow: 1, justifyContent: "flex-end", paddingHorizontal: spacing.md, gap: spacing.sm },
    state: { alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.lg, paddingVertical: spacing.xl, gap: spacing.sm },
    stateIcon: { width: 72, height: 72, borderRadius: 36, alignItems: "center", justifyContent: "center", backgroundColor: colors.primaryMuted },
    stateIconText: { color: colors.primary, fontSize: 28, fontWeight: "900" },
    stateTitle: { color: colors.text, fontSize: 22, lineHeight: 28, fontWeight: "800", textAlign: "center" },
    stateBody: { color: colors.stateText, fontSize: 15, lineHeight: 21, textAlign: "center", maxWidth: 360 },
    statusBar: { alignSelf: "center", borderRadius: 14, paddingHorizontal: 10, paddingVertical: 5, backgroundColor: colors.surfaceOverlay, borderColor: colors.borderSoft, borderWidth: 1 },
    statusText: { color: colors.stateText, fontSize: 11, lineHeight: 14, fontWeight: "700" },
    historyRow: { flexDirection: "row", gap: 7, paddingVertical: spacing.xs },
    historyCard: { minWidth: 150, maxWidth: 220, borderRadius: 14, padding: 9, backgroundColor: colors.surfaceOverlay, borderWidth: 1, borderColor: colors.borderSoft },
    historyCardActive: { borderColor: colors.primary, backgroundColor: colors.primaryMuted },
    historyTitle: { color: colors.text, fontSize: 12, lineHeight: 16, fontWeight: "800" },
    historyMeta: { color: colors.mutedText, fontSize: 10, lineHeight: 13, marginTop: 3 },
    messageBlock: { alignItems: "flex-start", gap: 4 },
    messageBlockMine: { alignItems: "flex-end" },
    messageBubble: { maxWidth: "82%", borderRadius: 18, borderBottomLeftRadius: 7, paddingHorizontal: 12, paddingVertical: 9, gap: 5, backgroundColor: colors.surfaceOverlay, borderWidth: 1, borderColor: colors.borderSoft },
    messageBubbleMine: { borderBottomLeftRadius: 18, borderBottomRightRadius: 7, backgroundColor: colors.primaryMuted, borderColor: colors.primaryMuted },
    author: { color: colors.primary, fontSize: 11, lineHeight: 14, fontWeight: "800" },
    messageText: { color: colors.text, fontSize: 15, lineHeight: 21 },
    messageMeta: { color: colors.mutedText, fontSize: 10, lineHeight: 13, alignSelf: "flex-end" },
    attachmentImage: { width: 220, height: 170, borderRadius: 13, backgroundColor: colors.surfaceMuted },
    attachmentName: { color: colors.stateText, fontSize: 11, lineHeight: 15 },
})
