import { useRef } from "react"
import { ImageBackground, useWindowDimensions, View } from "react-native"
import { useTheme } from "@/providers/theme-provider"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { CHAT_BACKGROUND_DARK, CHAT_BACKGROUND_LIGHT } from "@/screens/chat/chat-screen.constants"
import { createChatScreenStyles } from "@/screens/chat/chat-screen.styles"

/** Mounted once, outside keyboard resizing and content animations. */
export function ChatBackdrop() {
    const { isDark, themeName } = useTheme()
    const styles = useThemeStyles(createChatScreenStyles)
    const { width, height } = useWindowDimensions()
    const canvas = useRef({ width, height })
    // Android resizes its entire window for the keyboard. Preserve the wallpaper
    // scale until rotation or a wider/narrower window establishes a new canvas.
    canvas.current = width !== canvas.current.width ? { width, height } : { width, height: Math.max(height, canvas.current.height) }
    return <View testID="chat-backdrop" pointerEvents="none" style={[styles.backgroundImage, { bottom: undefined, height: canvas.current.height }]}>
        <ImageBackground imageStyle={styles.backgroundImageAsset} resizeMode="cover" source={CHAT_BACKGROUND_LIGHT} style={[styles.backgroundImage, themeName === "dark" ? styles.backgroundImageHidden : null]} />
        <ImageBackground imageStyle={styles.backgroundImageAsset} resizeMode="cover" source={CHAT_BACKGROUND_DARK} style={[styles.backgroundImage, themeName === "dark" ? null : styles.backgroundImageHidden]} />
        <View style={[styles.backgroundScrim, isDark ? styles.backgroundScrimDark : styles.backgroundScrimLight]} />
    </View>
}
