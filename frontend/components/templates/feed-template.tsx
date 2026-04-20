import { ScrollView, View } from "react-native"

import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { screenTemplateStyles } from "@/components/templates/screen-template.styles"
import type { FeedTemplateProps } from "@/components/templates/screen-template.types"

export function FeedTemplate({
    children,
    chromeTemplate,
    contentContainerStyle,
    scrollViewStyle,
    showsVerticalScrollIndicator = false,
    style,
}: FeedTemplateProps) {
    useApplyScreenTemplate("feed", chromeTemplate)

    return (
        <View style={[screenTemplateStyles.screen, style]}>
            <ScrollView
                contentContainerStyle={contentContainerStyle}
                showsVerticalScrollIndicator={showsVerticalScrollIndicator}
                style={[screenTemplateStyles.scroll, scrollViewStyle]}
            >
                {children}
            </ScrollView>
        </View>
    )
}
