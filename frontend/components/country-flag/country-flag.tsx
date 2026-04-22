import { CountryFlagProps } from "@/components/country-flag/country-flag.types"
import {
    COUNTRY_FLAG_ASPECT_RATIO,
    COUNTRY_FLAGS,
} from "@/components/country-flag/country-flag.consts"
import { isDimensionValue } from "@/components/country-flag/country-flag.utils"
import { StyleSheet, View, type ViewStyle } from "react-native"

export function CountryFlag(props: CountryFlagProps) {
    const { code, style } = props
    const Flag = COUNTRY_FLAGS[code]
    const aspectRatio = COUNTRY_FLAG_ASPECT_RATIO
    const flattenedStyle = StyleSheet.flatten(style)
    const styleWidth = isDimensionValue(flattenedStyle?.width) ? flattenedStyle.width : undefined
    const styleHeight = isDimensionValue(flattenedStyle?.height) ? flattenedStyle.height : undefined

    const sizeStyle: ViewStyle = { aspectRatio }

    if ("width" in props) {
        sizeStyle.width = props.width
    } else if ("height" in props) {
        sizeStyle.height = props.height
    } else if (styleWidth != null) {
        sizeStyle.width = styleWidth
    } else if (styleHeight != null) {
        sizeStyle.height = styleHeight
    } else {
        sizeStyle.width = 24
    }

    return (
        <View
            collapsable={false}
            style={[
                style,
                sizeStyle,
            ]}
        >
            <Flag width="100%" height="100%" />
        </View>
    )
}
