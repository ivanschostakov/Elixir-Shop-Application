import { useCallback, useEffect, useRef } from "react"
import { useActionSheet } from "@expo/react-native-action-sheet"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"

export type AppSheetAction = { id: string; label: string; onPress: () => void; disabled?: boolean; destructive?: boolean }
type Options = { actions: readonly AppSheetAction[]; title?: string; anchor?: number; onClose?: () => void }
export function useAppActionSheet() {
    const { showActionSheetWithOptions } = useActionSheet()
    const { isDark, palette } = useTheme()
    const { t } = useLanguage()
    return useCallback(({ actions, title, anchor, onClose }: Options) => {
        showActionSheetWithOptions({
            title, anchor, options: [...actions.map(action => action.label), t("common.cancel")],
            cancelButtonIndex: actions.length,
            disabledButtonIndices: actions.flatMap((action, index) => action.disabled ? [index] : []),
            destructiveButtonIndex: actions.flatMap((action, index) => action.destructive ? [index] : []),
            userInterfaceStyle: isDark ? "dark" : "light", useModal: true,
            containerStyle: { backgroundColor: palette.surface }, textStyle: { color: palette.text },
        }, index => {
            onClose?.()
            if (index === undefined) return
            const action = actions[index]
            if (action && !action.disabled) action.onPress()
        })
    }, [isDark, palette.surface, palette.text, showActionSheetWithOptions, t])
}
export function AppActionSheet({ visible, ...options }: Options & { visible: boolean }) {
    const show = useAppActionSheet()
    const open = useRef(false), latest = useRef(options)
    latest.current = options
    useEffect(() => {
        if (!visible || open.current) return
        open.current = true
        show({ ...latest.current, onClose: () => { open.current = false; latest.current.onClose?.() } })
    }, [show, visible])
    return null
}
