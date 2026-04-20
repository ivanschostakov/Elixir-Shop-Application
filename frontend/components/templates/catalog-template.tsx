import { View } from "react-native"

import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { screenTemplateStyles } from "@/components/templates/screen-template.styles"
import type { TemplateContainerProps } from "@/components/templates/screen-template.types"

export function CatalogTemplate({ children, chromeTemplate, style }: TemplateContainerProps) {
    useApplyScreenTemplate("catalog", chromeTemplate)

    return <View style={[screenTemplateStyles.screen, style]}>{children}</View>
}
