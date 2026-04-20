import { useEffect, useState } from "react"
import {
    ActivityIndicator,
    Image,
    Pressable,
    Text,
    View,
    type ImageSourcePropType,
} from "react-native"
import { Path, Svg } from "react-native-svg"

import { stickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { translate } from "@/i18n/translations"
import { deliveryScreenStyles } from "@/screens/delivery/delivery-screen.styles"

type DeliveryInfoRow = {
    key: string
    label: string
    value: string
}

type DeliveryProviderOption = {
    imageAlt?: string
    imageSource?: ImageSourcePropType
    key: string
    label: string
}

type PickupPointFooterExtensionProps = {
    actionLabel?: string
    error?: string | null
    inset?: boolean
    isResolving?: boolean
    isProviderSelectionDisabled?: boolean
    onChoose: () => void
    onClose: () => void
    onCopyInfo: (value: string) => void
    onOpenOfficePage?: (() => void) | null
    onSelectProvider?: ((providerKey: string) => void) | null
    providerOptions?: DeliveryProviderOption[]
    rows: DeliveryInfoRow[]
    selectedProviderKey?: string | null
    title: string
}

export function PickupPointFooterExtension({
    actionLabel = translate("delivery.pickupPointChoose"),
    error = null,
    inset = false,
    isResolving = false,
    isProviderSelectionDisabled = false,
    onChoose,
    onClose,
    onCopyInfo,
    onOpenOfficePage = null,
    onSelectProvider = null,
    providerOptions = [],
    rows,
    selectedProviderKey = null,
    title,
}: PickupPointFooterExtensionProps) {
    const shouldShowProviderOptions =
        providerOptions.length > 1 && selectedProviderKey !== null && onSelectProvider !== null
    const selectProvider = onSelectProvider ?? (() => {})
    const [failedProviderImages, setFailedProviderImages] = useState<Record<string, boolean>>({})

    useEffect(() => {
        setFailedProviderImages({})
    }, [providerOptions])

    return (
        <View
            style={[
                deliveryScreenStyles.pickupFooterExtension,
                inset && deliveryScreenStyles.pickupFooterExtensionInset,
            ]}
        >
            <View style={deliveryScreenStyles.pickupFooterHeaderRow}>
                <View style={deliveryScreenStyles.pickupFooterHeaderText}>
                    {onOpenOfficePage ? (
                        <Pressable
                            accessibilityLabel={translate("delivery.pickupPointOfficePage")}
                            accessibilityRole="link"
                            hitSlop={6}
                            onPress={onOpenOfficePage}
                            style={({ pressed }) => [
                                deliveryScreenStyles.pickupFooterTitleButton,
                                pressed && deliveryScreenStyles.pickupFooterTitleButtonPressed,
                            ]}
                        >
                            <Text style={deliveryScreenStyles.pickupFooterTitle}>
                                {title}
                            </Text>
                        </Pressable>
                    ) : (
                        <Text style={deliveryScreenStyles.pickupFooterTitle}>
                            {title}
                        </Text>
                    )}
                </View>

                <Pressable
                    accessibilityLabel={translate("common.close")}
                    accessibilityRole="button"
                    hitSlop={8}
                    onPress={onClose}
                    style={({ pressed }) => [
                        deliveryScreenStyles.pickupFooterCloseButton,
                        pressed && deliveryScreenStyles.pickupFooterCloseButtonPressed,
                    ]}
                >
                    <Svg width={18} height={18} viewBox="0 0 24 24" fill="none">
                        <Path
                            d="M7 7L17 17M17 7L7 17"
                            stroke="#111111"
                            strokeLinecap="round"
                            strokeWidth={2.75}
                        />
                    </Svg>
                </Pressable>
            </View>

            {shouldShowProviderOptions ? (
                <View style={deliveryScreenStyles.pickupFooterProviderRow}>
                    {providerOptions.map((providerOption) => {
                        const isSelected = providerOption.key === selectedProviderKey

                        return (
                            <Pressable
                                key={providerOption.key}
                                accessibilityLabel={providerOption.label}
                                accessibilityRole="button"
                                disabled={isProviderSelectionDisabled}
                                onPress={() => {
                                    if (!isSelected) {
                                        selectProvider(providerOption.key)
                                    }
                                }}
                                style={({ pressed }) => [
                                    deliveryScreenStyles.pickupFooterProviderButton,
                                    isSelected && deliveryScreenStyles.pickupFooterProviderButtonActive,
                                    isProviderSelectionDisabled
                                        && deliveryScreenStyles.pickupFooterProviderButtonDisabled,
                                    pressed
                                        && !isProviderSelectionDisabled
                                        && deliveryScreenStyles.pickupFooterProviderButtonPressed,
                                ]}
                            >
                                {providerOption.imageSource && !failedProviderImages[providerOption.key] ? (
                                    <Image
                                        accessibilityIgnoresInvertColors
                                        accessibilityLabel={providerOption.imageAlt ?? providerOption.label}
                                        source={providerOption.imageSource}
                                        style={deliveryScreenStyles.pickupFooterProviderButtonImage}
                                        onError={() => {
                                            setFailedProviderImages((currentImages) => ({
                                                ...currentImages,
                                                [providerOption.key]: true,
                                            }))
                                        }}
                                    />
                                ) : (
                                    <Text
                                        style={[
                                            deliveryScreenStyles.pickupFooterProviderButtonText,
                                            isSelected
                                                && deliveryScreenStyles.pickupFooterProviderButtonTextActive,
                                        ]}
                                    >
                                        {providerOption.imageAlt ?? providerOption.label}
                                    </Text>
                                )}
                            </Pressable>
                        )
                    })}
                </View>
            ) : null}

            {isResolving ? (
                <View
                    style={[
                        deliveryScreenStyles.pickupFooterStatusRow,
                        inset && deliveryScreenStyles.pickupFooterPrimaryRowInsetReset,
                    ]}
                >
                    <ActivityIndicator color="#FFFFFF" size="small" />
                </View>
            ) : (
                <>
                    {rows.length > 0 ? (
                        <View style={deliveryScreenStyles.pickupFooterInfoList}>
                            {rows.map((row) => (
                                <Pressable
                                    key={row.key}
                                    accessibilityLabel={row.label}
                                    accessibilityRole="button"
                                    onPress={() => {
                                        void onCopyInfo(row.value)
                                    }}
                                    style={({ pressed }) => [
                                        deliveryScreenStyles.pickupFooterInfoRow,
                                        pressed && deliveryScreenStyles.pickupFooterInfoRowPressed,
                                    ]}
                                >
                                    <Text style={deliveryScreenStyles.pickupFooterInfoValue}>
                                        {row.value}
                                    </Text>
                                </Pressable>
                            ))}
                        </View>
                    ) : null}

                    {error ? (
                        <View style={deliveryScreenStyles.pickupFooterErrorBox}>
                            <Text style={deliveryScreenStyles.pickupFooterErrorText}>
                                {error}
                            </Text>
                        </View>
                    ) : null}

                    {rows.length > 0 ? (
                        <View
                            style={[
                                deliveryScreenStyles.pickupFooterActionsRow,
                                inset && deliveryScreenStyles.pickupFooterPrimaryRowInsetReset,
                            ]}
                        >
                            <Pressable
                                accessibilityLabel={actionLabel}
                                accessibilityRole="button"
                                onPress={onChoose}
                                style={({ pressed }) => [
                                    stickyFooterStyles.actionButton,
                                    pressed && stickyFooterStyles.actionButtonPressed,
                                ]}
                            >
                                <Text style={stickyFooterStyles.actionButtonText}>
                                    {actionLabel}
                                </Text>
                            </Pressable>
                        </View>
                    ) : null}
                </>
            )}
        </View>
    )
}
