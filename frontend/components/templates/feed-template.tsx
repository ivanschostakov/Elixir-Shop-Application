import { Animated, ScrollView } from "react-native"

import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { createScreenTemplateStyles } from "@/components/templates/screen-template.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
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
    const screenTemplateStyles = useThemeStyles(createScreenTemplateStyles)
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
