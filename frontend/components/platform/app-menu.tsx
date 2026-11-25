import { Platform, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native"
import Svg, { Path } from "react-native-svg"
import { AppSurface } from "@/components/platform/app-surface"
import { useAppActionSheet } from "@/components/platform/app-action-sheet"
// The Play binary has no native menu view. Metro drops this import on Android.
const MenuView: typeof import("@react-native-menu/menu").MenuView | null = Platform.OS === "ios"
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    ? require("@react-native-menu/menu").MenuView : null
type Option = { id: string; label: string; detail?: string; disabled?: boolean }
type Props = { label: string; options: readonly Option[]; value?: string; onChange: (id: string) => void; dark: boolean; color: string; fallbackColor: string; style?: StyleProp<ViewStyle> }
export function AppMenu({ label, options, value, onChange, dark, color, fallbackColor, style }: Props) {
    const showActionSheet = useAppActionSheet()
    const expandedLabel = (option: Option) => `${option.id === value ? "✓ " : ""}${option.label}${option.detail ? ` · ${option.detail}` : ""}`
    const trigger = (
        <View style={styles.trigger}>
            <AppSurface dark={dark} fallbackColor={fallbackColor} pointerEvents="none" style={StyleSheet.absoluteFill} />
            <Svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" accessible={false}><Path d="M3 10a9 9 0 1 1 0 5M3 4v6h6M12 7v5l3 2" /></Svg>
            <Text numberOfLines={1} style={{ color, fontSize: 16, fontWeight: "600" }}>{label}</Text>
        </View>
    )
    if (!MenuView) {
        return <Pressable accessibilityRole="button" accessibilityLabel={label} style={style}
            onPress={() => showActionSheet({ title: label, actions: options.map(option => ({
                id: option.id, label: expandedLabel(option), disabled: option.disabled,
                onPress: () => onChange(option.id),
            })) })}>
            {trigger}
        </Pressable>
    }
    return <MenuView themeVariant={dark ? "dark" : "light"} shouldOpenOnLongPress={false}
        actions={options.map(option => ({
            id: option.id,
            title: option.label,
            subtitle: option.detail,
            state: option.id === value ? "on" : "off",
            attributes: { disabled: option.disabled },
        }))}
        onPressAction={({ nativeEvent }) => {
            if (options.some(option => option.id === nativeEvent.event && !option.disabled)) onChange(nativeEvent.event)
        }} style={style}>
        <View accessible accessibilityRole="button" accessibilityLabel={label}>{trigger}</View>
    </MenuView>
}
const styles = StyleSheet.create({ trigger: { minHeight: 44, flexDirection: "row", gap: 8, alignItems: "center", justifyContent: "center", paddingHorizontal: 16 } })
