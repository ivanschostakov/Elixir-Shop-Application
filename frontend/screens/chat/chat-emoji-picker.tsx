import { Pressable, Text, View } from "react-native"

import { useLanguage } from "@/providers/language-provider"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { createChatScreenStyles } from "@/screens/chat/chat-screen.styles"

export const COMMUNITY_REACTION_EMOJIS = ["👍", "❤️", "🔥", "😂", "👏", "😮", "😢", "🙏"] as const

const CHAT_INPUT_EMOJIS = [
    "😀", "😃", "😄", "😁", "😂", "🥰", "😍", "😘",
    "😊", "😉", "🙂", "🤗", "🤔", "😮", "😢", "😭",
    "👍", "👎", "👏", "🙏", "💪", "🔥", "❤️", "💯",
    "🎉", "✨", "✅", "💊", "🧬", "💉", "🌿", "☀️",
] as const

export function ChatEmojiPicker({ onSelect }: { onSelect: (emoji: string) => void }) {
    const styles = useThemeStyles(createChatScreenStyles)
    const { t } = useLanguage()
    return (
        <View accessibilityLabel={t("chat.emojiPickerLabel")} style={styles.emojiPicker}>
            <Text style={styles.emojiPickerTitle}>{t("chat.emojiPickerTitle")}</Text>
            <View style={styles.emojiPickerGrid}>
                {CHAT_INPUT_EMOJIS.map((emoji) => (
                    <Pressable accessibilityLabel={emoji} key={emoji} onPress={() => onSelect(emoji)} style={({ pressed }) => [styles.emojiPickerButton, pressed ? styles.emojiPickerButtonPressed : null]}>
                        <Text style={styles.emojiPickerEmoji}>{emoji}</Text>
                    </Pressable>
                ))}
            </View>
        </View>
    )
}
