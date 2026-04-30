import { View } from "react-native"

import { EmptyState } from "@/components/content/empty-state"
import { SmileBubbleIcon } from "@/components/footer/sticky-footer.icons"
import { FeedTemplate } from "@/components/templates/feed-template"
import { useLanguage } from "@/providers/language-provider"
import { colors } from "@/theme/colors"
import { chatScreenStyles } from "./chat-screen.styles"

export default function ChatScreen() {
    const { t } = useLanguage()

    return (
        <FeedTemplate
            contentContainerStyle={chatScreenStyles.content}
            scrollViewStyle={chatScreenStyles.container}
        >
            <View style={chatScreenStyles.emptyWrap}>
                <EmptyState
                    illustration={
                        <View style={chatScreenStyles.iconWrap}>
                            <SmileBubbleIcon color={colors.primary} />
                        </View>
                    }
                    title={t("chat.title")}
                    description={t("chat.description")}
                    variant="plain"
                />
            </View>
        </FeedTemplate>
    )
}
