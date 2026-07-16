import { Animated } from "react-native"

import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { createScreenTemplateStyles } from "@/components/templates/screen-template.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import type { TemplateContainerProps } from "@/components/templates/screen-template.types"
import { useEntranceAnimation } from "@/hooks/animation/use-entrance-animation"

export function DetailTemplate({ children, chromeTemplate, style }: TemplateContainerProps) {
    const screenTemplateStyles = useThemeStyles(createScreenTemplateStyles)
    useApplyScreenTemplate("detail", chromeTemplate)
    const entranceStyle = useEntranceAnimation({ translateY: 6 })

    return <Animated.View style={[screenTemplateStyles.screen, style, entranceStyle]}>{children}</Animated.View>
}
