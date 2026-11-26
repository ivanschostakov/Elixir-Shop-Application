import { ScrollView, StyleSheet, type StyleProp, type ViewStyle } from "react-native"
import { AppBlurSurface } from "@/components/platform/app-blur-surface"

export function AppEdgeMaterial({ dark, topEdge = false, style }: {
    dark: boolean
    topEdge?: boolean
    style: StyleProp<ViewStyle>
}) {
    // Android's fading edge masks the live blur towards the conversation.
    // Only the material is inside this view, so controls stay sharp and tappable.
    return <ScrollView pointerEvents="none" importantForAccessibility="no-hide-descendants"
        scrollEnabled={false} showsVerticalScrollIndicator={false} overScrollMode="never"
        fadingEdgeLength={topEdge ? { start: 0, end: 32 } : { start: 32, end: 0 }}
        style={style} contentContainerStyle={styles.fill}>
        <AppBlurSurface androidBlur intensity={40} tint={dark ? "systemUltraThinMaterialDark" : "systemUltraThinMaterialLight"} style={styles.fill} />
    </ScrollView>
}

const styles = StyleSheet.create({ fill: { flex: 1 } })
