import { Pressable, Text } from "react-native"
import { Path, Svg } from "react-native-svg"

import type { DeliveryCornerButtonProps } from "@/components/delivery/delivery-corner-button.types"
import { createDeliveryScreenStyles } from "@/screens/delivery/delivery-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"

export function DeliveryCornerButton({
    accessibilityLabel,
    iconPath,
    isActive = false,
    label,
    onPress,
}: DeliveryCornerButtonProps) {
    const deliveryScreenStyles = useThemeStyles(createDeliveryScreenStyles)
    const { palette } = useTheme()
    return (
        <Pressable
            accessibilityLabel={accessibilityLabel}
            accessibilityRole="button"
            accessibilityState={{ selected: isActive }}
            hitSlop={12}
            onPress={onPress}
            style={({ pressed }) => [
                deliveryScreenStyles.cornerButton,
                isActive && deliveryScreenStyles.cornerButtonActive,
                pressed && deliveryScreenStyles.cornerButtonPressed,
            ]}
        >
            {label ? (
                <Text
                    style={[
                        deliveryScreenStyles.cornerButtonLabel,
                        isActive && deliveryScreenStyles.cornerButtonLabelActive,
                    ]}
                >
                    {label}
                </Text>
            ) : iconPath ? (
                <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                    <Path d={iconPath} fill={isActive ? palette.onPrimary : palette.primary} />
                </Svg>
            ) : null}
        </Pressable>
    )
}
