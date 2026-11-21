import type { ReactNode } from "react"
import { Pressable, View } from "react-native"
import { createStickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"

export type FooterNavItem = { key: string; accessibilityLabel: string; icon: ReactNode; isActive: boolean; onPress: () => void }

/** Shared navigation geometry for the main app and the mentor. */
export function FooterNavRow({ items, tabs = false }: { items: FooterNavItem[]; tabs?: boolean }) {
    const styles = useThemeStyles(createStickyFooterStyles)
    return <View accessibilityRole={tabs ? "tablist" : undefined} style={styles.navRow}>
        {items.map(item => <View key={item.key} style={styles.footerItem}>
            <Pressable accessibilityLabel={item.accessibilityLabel} accessibilityRole={tabs ? "tab" : "button"} accessibilityState={tabs ? { selected: item.isActive } : undefined}
                onPress={item.onPress} style={({ pressed }) => [styles.iconButton, item.isActive && pressed && styles.iconButtonPressed]}>{item.icon}</Pressable>
        </View>)}
    </View>
}
