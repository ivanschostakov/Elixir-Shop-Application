import { Animated, ScrollView } from "react-native"

import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { screenTemplateStyles } from "@/components/templates/screen-template.styles"
import type { FeedTemplateProps } from "@/components/templates/screen-template.types"
import { useEntranceAnimation } from "@/hooks/animation/use-entrance-animation"

export function FeedTemplate({
    children,
    chromeTemplate,
    contentContainerStyle,
    scrollViewStyle,
    showsVerticalScrollIndicator = false,
    style,
}: FeedTemplateProps) {
    useApplyScreenTemplate("feed", chromeTemplate)
    const entranceStyle = useEntranceAnimation({ translateY: 6 })

    return (
        <Animated.View style={[screenTemplateStyles.screen, style, entranceStyle]}>
            <ScrollView
                contentContainerStyle={contentContainerStyle}
                showsVerticalScrollIndicator={showsVerticalScrollIndicator}
                style={[screenTemplateStyles.scroll, scrollViewStyle]}
            >
                {children}
            </ScrollView>
        </Animated.View>
    )
}
