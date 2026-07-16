import { View } from "react-native"
import { Path, Svg } from "react-native-svg"

import {
    DELIVERY_SUGGEST_ICON_DEFINITIONS,
    DELIVERY_SUGGEST_ICON_SIZE,
    getDeliverySuggestIconName,
} from "@/components/delivery/delivery-suggest-icon.constants"
import type { DeliverySuggestIconProps } from "@/components/delivery/delivery-suggest-icon.types"
import { createDeliveryScreenStyles } from "@/screens/delivery/delivery-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"

export function DeliverySuggestIcon({ result }: DeliverySuggestIconProps) {
    const deliveryScreenStyles = useThemeStyles(createDeliveryScreenStyles)
    const iconName = getDeliverySuggestIconName(result)
    const iconDefinition = DELIVERY_SUGGEST_ICON_DEFINITIONS[iconName]

    return (
        <View
            style={[
                deliveryScreenStyles.resultIconBadge,
                { backgroundColor: iconDefinition.backgroundColor },
            ]}
        >
            <Svg
                width={DELIVERY_SUGGEST_ICON_SIZE}
                height={DELIVERY_SUGGEST_ICON_SIZE}
                viewBox={iconDefinition.viewBox}
                fill="none"
            >
                {iconDefinition.layers.map((layer, index) => (
                    <Path
                        key={`${iconName}-${index}`}
                        d={layer.d}
                        fill={layer.fill}
                        stroke={layer.stroke}
                        strokeLinecap={layer.strokeLinecap}
                        strokeLinejoin={layer.strokeLinejoin}
                        strokeWidth={layer.strokeWidth}
                    />
                ))}
            </Svg>
        </View>
    )
}
