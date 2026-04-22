import { View } from "react-native"

import { FULLSCREEN_CHROME_TEMPLATE } from "@/components/templates/map-flow-template.constants"
import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { screenTemplateStyles } from "@/components/templates/screen-template.styles"
import type { MapFlowTemplateProps } from "@/components/templates/screen-template.types"

export function MapFlowTemplate({ children, chromeOverlay, overlay, style }: MapFlowTemplateProps) {
    useApplyScreenTemplate("map-flow", FULLSCREEN_CHROME_TEMPLATE)

    return (
        <View style={[screenTemplateStyles.fullscreen, style]}>
            {children}
            {chromeOverlay ? (
                <View pointerEvents="box-none" style={screenTemplateStyles.chromeOverlay}>
                    {chromeOverlay}
                </View>
            ) : null}
            {overlay}
        </View>
    )
}
