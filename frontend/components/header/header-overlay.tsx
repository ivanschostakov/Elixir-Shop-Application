import type { ReactNode } from "react"
import { Modal, Pressable, StyleSheet } from "react-native"
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context"
import { useTheme } from "@/providers/theme-provider"

// A header-sized parent clips native touch and accessibility bounds, even with overflow: visible.
export function HeaderOverlay({ children, onClose, closeLabel }: { children: ReactNode; onClose: () => void; closeLabel: string }) {
    const { palette } = useTheme()
    return <Modal transparent animationType="fade" statusBarTranslucent navigationBarTranslucent onRequestClose={onClose}>
        <SafeAreaProvider>
            <Pressable accessibilityRole="button" accessibilityLabel={closeLabel} onPress={onClose}
                style={[StyleSheet.absoluteFill, { backgroundColor: palette.veilSoft }]} />
            <SafeAreaView pointerEvents="box-none" onAccessibilityEscape={onClose} style={styles.content}>
                {children}
            </SafeAreaView>
        </SafeAreaProvider>
    </Modal>
}

const styles = StyleSheet.create({ content: { flex: 1, paddingHorizontal: 16, paddingVertical: 8 } })
