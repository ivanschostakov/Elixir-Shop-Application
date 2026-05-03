import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
    ActivityIndicator,
    Animated,
    Image,
    Linking,
    Pressable,
    ScrollView,
    type StyleProp,
    Text,
    View,
    type ViewStyle,
} from "react-native"
import RenderHtml from "react-native-render-html"
import Svg, { Path } from "react-native-svg"

import { colors } from "@/theme/colors"
import { motion } from "@/theme/motion"
import { chatScreenStyles } from "@/screens/chat/chat-screen.styles"
import { SAFE_LINK_PROTOCOL_PATTERN } from "@/screens/chat/chat-screen.constants"
import { markdownToHtml } from "@/screens/chat/chat-markdown"
import MicrophoneSvgIcon from "@/assets/icons/chat/microphone-alt-svgrepo-com.svg"
import type {
    AIInteractiveAction,
    AIInteractivePayload,
    AIInteractiveProductCard,
    AIInteractiveVariant,
} from "@/services/api/ai-chat.types"
import type { BasketItemRead, BasketRead } from "@/types/basket"

export function AnimatedMessageBlock({ children }: { children: ReactNode }) {
    const progress = useRef(new Animated.Value(0)).current

    useEffect(() => {
        Animated.timing(progress, {
            duration: motion.duration.enter,
            easing: motion.easing.enter,
            toValue: 1,
            useNativeDriver: true,
        }).start()
    }, [progress])

    return (
        <Animated.View
            style={{
                opacity: progress,
                transform: [
                    {
                        translateY: progress.interpolate({
                            inputRange: [0, 1],
                            outputRange: [8, 0],
                        }),
                    },
                ],
            }}
        >
            {children}
        </Animated.View>
    )
}

export function AiTypingBubble() {
    const dotProgressValues = useRef([
        new Animated.Value(0),
        new Animated.Value(0),
        new Animated.Value(0),
    ]).current

    useEffect(() => {
        const animations = dotProgressValues.map((dotProgress, dotIndex) =>
            Animated.loop(
                Animated.sequence([
                    Animated.delay(dotIndex * 120),
                    Animated.timing(dotProgress, {
                        duration: 320,
                        easing: motion.easing.standard,
                        toValue: 1,
                        useNativeDriver: true,
                    }),
                    Animated.timing(dotProgress, {
                        duration: 320,
                        easing: motion.easing.standard,
                        toValue: 0,
                        useNativeDriver: true,
                    }),
                    Animated.delay((2 - dotIndex) * 120),
                ]),
            ),
        )

        animations.forEach((animation) => animation.start())

        return () => {
            animations.forEach((animation) => animation.stop())
        }
    }, [dotProgressValues])

    return (
        <View style={[chatScreenStyles.messageBubble, chatScreenStyles.aiMessageBubble, chatScreenStyles.typingBubble]}>
            <View style={chatScreenStyles.typingDotsRow}>
                {dotProgressValues.map((dotProgress, dotIndex) => (
                    <Animated.View
                        key={dotIndex}
                        style={[
                            chatScreenStyles.typingDot,
                            {
                                opacity: dotProgress.interpolate({
                                    inputRange: [0, 1],
                                    outputRange: [0.35, 1],
                                }),
                                transform: [
                                    {
                                        translateY: dotProgress.interpolate({
                                            inputRange: [0, 1],
                                            outputRange: [0, -3],
                                        }),
                                    },
                                ],
                            },
                        ]}
                    />
                ))}
            </View>
        </View>
    )
}

export function MessageMarkdown({
    hasImageAttachments,
    isUserMessage,
    markdown,
    onOpenLink,
    width,
}: {
    hasImageAttachments: boolean
    isUserMessage: boolean
    markdown: string
    onOpenLink?: (href: string) => void
    width: number
}) {
    const htmlSource = useMemo(() => ({ html: markdownToHtml(markdown) }), [markdown])
    const textColor = isUserMessage ? "#17311C" : "#15191E"
    const markdownWrapStyle = hasImageAttachments ? chatScreenStyles.messageMarkdownWithMedia : null
    const messageBaseStyle = {
        ...chatScreenStyles.messageText,
        ...chatScreenStyles.messageMarkdownBaseText,
        ...(isUserMessage ? chatScreenStyles.userMessageText : {}),
    }

    return (
        <View style={markdownWrapStyle}>
            <RenderHtml
                baseStyle={messageBaseStyle}
                contentWidth={width}
                enableExperimentalMarginCollapsing
                renderersProps={{
                    a: {
                        onPress: (_event, href) => {
                            if (!href) {
                                return
                            }
                            if (onOpenLink) {
                                onOpenLink(href)
                                return
                            }
                            if (SAFE_LINK_PROTOCOL_PATTERN.test(href)) {
                                void Linking.openURL(href).catch(() => undefined)
                            }
                        },
                    },
                }}
                source={htmlSource}
                tagsStyles={{
                    a: {
                        color: "#0A84FF",
                        textDecorationLine: "underline",
                    },
                    blockquote: {
                        borderLeftColor: "rgba(95,115,128,0.45)",
                        borderLeftWidth: 3,
                        marginBottom: 0,
                        marginTop: 0,
                        paddingLeft: 10,
                    },
                    code: {
                        backgroundColor: "rgba(34,39,46,0.12)",
                        borderRadius: 4,
                        color: textColor,
                        paddingHorizontal: 4,
                        paddingVertical: 1,
                    },
                    h1: {
                        color: textColor,
                        fontSize: 22,
                        fontWeight: "700",
                        lineHeight: 28,
                        marginBottom: 6,
                        marginTop: 0,
                    },
                    h2: {
                        color: textColor,
                        fontSize: 20,
                        fontWeight: "700",
                        lineHeight: 26,
                        marginBottom: 6,
                        marginTop: 0,
                    },
                    h3: {
                        color: textColor,
                        fontSize: 18,
                        fontWeight: "700",
                        lineHeight: 24,
                        marginBottom: 6,
                        marginTop: 0,
                    },
                    li: {
                        color: textColor,
                        lineHeight: 22,
                        marginBottom: 1,
                    },
                    ol: {
                        marginBottom: 0,
                        marginTop: 0,
                        paddingLeft: 18,
                    },
                    p: {
                        color: textColor,
                        lineHeight: 22,
                        marginBottom: 0,
                        marginTop: 0,
                    },
                    pre: {
                        backgroundColor: "rgba(34,39,46,0.12)",
                        borderRadius: 8,
                        color: textColor,
                        marginBottom: 0,
                        marginTop: 0,
                        paddingHorizontal: 9,
                        paddingVertical: 8,
                    },
                    strong: {
                        color: textColor,
                        fontWeight: "700",
                    },
                    ul: {
                        marginBottom: 0,
                        marginTop: 0,
                        paddingLeft: 18,
                    },
                }}
            />
        </View>
    )
}

function formatCommerceMoney(value: string | number, currency = "RUB") {
    const numericValue = Number(value)
    if (!Number.isFinite(numericValue)) {
        return `${value} ${currency}`.trim()
    }

    try {
        return new Intl.NumberFormat([], {
            currency,
            maximumFractionDigits: Number.isInteger(numericValue) ? 0 : 2,
            style: "currency",
        }).format(numericValue)
    } catch {
        return `${numericValue.toLocaleString()} ${currency}`.trim()
    }
}

function getPreferredAiVariantId(variants: AIInteractiveVariant[], basket: BasketRead | null) {
    const basketVariant = variants.find((variant) =>
        basket?.items.some((item) => item.variant_id === variant.id),
    )

    if (basketVariant) {
        return basketVariant.id
    }

    const firstAvailableVariant = variants.find((variant) => variant.in_stock && variant.stock > 0)
    return firstAvailableVariant?.id ?? variants[0]?.id ?? null
}

function getAiVariantStockLabel(variant: AIInteractiveVariant | null) {
    if (!variant) {
        return ""
    }

    if (!variant.in_stock || variant.stock <= 0) {
        return "Нет в наличии"
    }

    if (variant.stock <= 3) {
        return "Мало в наличии"
    }

    return "В наличии"
}

export function AIInteractiveContent({
    activeActionId,
    activeBasketVariantId,
    basket,
    onAddVariantToBasket,
    onActionPress,
    onBasketItemQuantityChange,
    onOpenProduct,
    payload,
}: {
    activeActionId: string | null
    activeBasketVariantId: number | null
    basket: BasketRead | null
    onAddVariantToBasket: (variant: AIInteractiveVariant) => void
    onActionPress: (action: AIInteractiveAction, quantity?: number) => void
    onBasketItemQuantityChange: (item: BasketItemRead, nextQuantity: number) => void
    onOpenProduct: (productId: number) => void
    payload: AIInteractivePayload
}) {
    const hasContent = payload.cards.length > 0
    if (!hasContent) {
        return null
    }

    return (
        <View style={chatScreenStyles.aiInteractiveWrap}>
            {payload.cards.map((card) => (
                <AIProductCard
                    activeActionId={activeActionId}
                    activeBasketVariantId={activeBasketVariantId}
                    basket={basket}
                    card={card}
                    key={card.id}
                    onAddVariantToBasket={onAddVariantToBasket}
                    onActionPress={onActionPress}
                    onBasketItemQuantityChange={onBasketItemQuantityChange}
                    onOpenProduct={onOpenProduct}
                />
            ))}
        </View>
    )
}

function AIProductCard({
    activeActionId,
    activeBasketVariantId,
    basket,
    card,
    onAddVariantToBasket,
    onActionPress,
    onBasketItemQuantityChange,
    onOpenProduct,
}: {
    activeActionId: string | null
    activeBasketVariantId: number | null
    basket: BasketRead | null
    card: AIInteractiveProductCard
    onAddVariantToBasket: (variant: AIInteractiveVariant) => void
    onActionPress: (action: AIInteractiveAction, quantity?: number) => void
    onBasketItemQuantityChange: (item: BasketItemRead, nextQuantity: number) => void
    onOpenProduct: (productId: number) => void
}) {
    const basketItemByVariantId = useMemo(
        () => new Map((basket?.items ?? []).map((item) => [item.variant_id, item])),
        [basket?.items],
    )
    const preferredVariantId = useMemo(
        () => getPreferredAiVariantId(card.variants, basket),
        [basket, card.variants],
    )
    const [selectedVariantId, setSelectedVariantId] = useState<number | null>(preferredVariantId)
    const visibleActions = useMemo(
        () => card.actions.filter((action) => action.type === "open_checkout"),
        [card.actions],
    )
    const actionsById = useMemo(() => new Map(visibleActions.map((action) => [action.id, action])), [visibleActions])
    const fallbackActionRows = useMemo(() => {
        const rows: { action_ids: string[] }[] = []
        for (let index = 0; index < visibleActions.length; index += 2) {
            rows.push({ action_ids: visibleActions.slice(index, index + 2).map((action) => action.id) })
        }
        return rows
    }, [visibleActions])
    const actionRows = useMemo(() => {
        const rows = card.action_rows?.length ? card.action_rows : fallbackActionRows
        return rows
            .map((row) => ({
                action_ids: row.action_ids.filter((actionId) => actionsById.has(actionId)),
            }))
            .filter((row) => row.action_ids.length > 0)
    }, [actionsById, card.action_rows, fallbackActionRows])
    const selectedVariant = card.variants.find((variant) => variant.id === selectedVariantId) ?? card.variants[0] ?? null
    const selectedBasketItem = selectedVariant ? basketItemByVariantId.get(selectedVariant.id) ?? null : null

    useEffect(() => {
        setSelectedVariantId((currentVariantId) => {
            if (currentVariantId !== null && card.variants.some((variant) => variant.id === currentVariantId)) {
                return currentVariantId
            }

            return preferredVariantId
        })
    }, [card.variants, preferredVariantId])

    const handleVariantSelect = useCallback((variant: AIInteractiveVariant) => {
        if (!variant.in_stock || variant.stock <= 0) {
            return
        }

        setSelectedVariantId(variant.id)
    }, [])

    return (
        <Pressable
            accessibilityLabel={card.title}
            accessibilityRole="button"
            onPress={() => onOpenProduct(card.product_id)}
            style={({ pressed }) => [
                chatScreenStyles.aiProductCard,
                pressed ? chatScreenStyles.aiProductCardPressed : null,
            ]}
        >
            <View style={chatScreenStyles.aiProductHeader}>
                <View style={chatScreenStyles.aiProductTextWrap}>
                    <Text numberOfLines={2} style={chatScreenStyles.aiProductTitle}>
                        {card.title}
                    </Text>
                </View>
            </View>
            {card.variants.length > 0 ? (
                <View style={chatScreenStyles.aiVariantSelectorCard}>
                    <ScrollView
                        contentContainerStyle={chatScreenStyles.aiVariantSelectorRow}
                        horizontal
                        showsHorizontalScrollIndicator={false}
                    >
                        {card.variants.map((variant) => {
                            const isSelected = variant.id === selectedVariant?.id
                            const isDisabled = !variant.in_stock || variant.stock <= 0

                            return (
                                <Pressable
                                    accessibilityLabel={variant.name}
                                    accessibilityRole="button"
                                    disabled={isDisabled}
                                    key={variant.id}
                                    onPress={(event) => {
                                        event.stopPropagation()
                                        handleVariantSelect(variant)
                                    }}
                                    style={({ pressed }) => [
                                        chatScreenStyles.aiVariantSelectorOption,
                                        isSelected ? chatScreenStyles.aiVariantSelectorOptionSelected : null,
                                        isDisabled ? chatScreenStyles.aiVariantSelectorOptionDisabled : null,
                                        pressed ? chatScreenStyles.aiVariantSelectorOptionPressed : null,
                                    ]}
                                >
                                    <Image
                                        resizeMode="cover"
                                        source={{ uri: variant.image_url || card.image_url }}
                                        style={[
                                            chatScreenStyles.aiVariantSelectorImage,
                                            isSelected ? chatScreenStyles.aiVariantSelectorImageSelected : null,
                                        ]}
                                    />
                                </Pressable>
                            )
                        })}
                    </ScrollView>
                    <View style={chatScreenStyles.aiSelectedVariantMetaRow}>
                        <View style={chatScreenStyles.aiSelectedVariantMetaCopy}>
                            <Text numberOfLines={1} style={chatScreenStyles.aiSelectedVariantName}>
                                {selectedVariant?.name ?? ""}
                            </Text>
                            <Text numberOfLines={1} style={chatScreenStyles.aiSelectedVariantStock}>
                                {getAiVariantStockLabel(selectedVariant)}
                            </Text>
                        </View>
                        {selectedVariant ? (
                            <Text style={chatScreenStyles.aiSelectedVariantPrice}>
                                {formatCommerceMoney(selectedVariant.price)}
                            </Text>
                        ) : null}
                    </View>
                    <AISelectedVariantBasketControl
                        active={selectedVariant ? activeBasketVariantId === selectedVariant.id : false}
                        basketItem={selectedBasketItem}
                        onAdd={() => {
                            if (selectedVariant) {
                                onAddVariantToBasket(selectedVariant)
                            }
                        }}
                        onQuantityChange={(item, nextQuantity) => onBasketItemQuantityChange(item, nextQuantity)}
                        variant={selectedVariant}
                    />
                </View>
            ) : null}
            {actionRows.length > 0 ? (
                <View style={chatScreenStyles.aiActionKeyboard}>
                    {actionRows.map((row, rowIndex) => {
                        const rowActions = row.action_ids
                            .map((actionId) => actionsById.get(actionId))
                            .filter((action): action is AIInteractiveAction => Boolean(action))
                        if (!rowActions.length) {
                            return null
                        }

                        return (
                            <View key={`${card.id}-row-${rowIndex}`} style={chatScreenStyles.aiActionKeyboardRow}>
                                {rowActions.map((action) => (
                                    <View key={action.id} style={chatScreenStyles.aiActionKeyboardCell}>
                                        <AIActionButton
                                            action={action}
                                            activeActionId={activeActionId}
                                            containerStyle={chatScreenStyles.aiKeyboardActionButton}
                                            onPress={() => onActionPress(action)}
                                        />
                                    </View>
                                ))}
                            </View>
                        )
                    })}
                </View>
            ) : null}
        </Pressable>
    )
}

function AISelectedVariantBasketControl({
    active,
    basketItem,
    onAdd,
    onQuantityChange,
    variant,
}: {
    active: boolean
    basketItem: BasketItemRead | null
    onAdd: () => void
    onQuantityChange: (item: BasketItemRead, nextQuantity: number) => void
    variant: AIInteractiveVariant | null
}) {
    const isUnavailable = !variant || !variant.in_stock || variant.stock <= 0
    const maxQuantity = basketItem
        ? Math.max(
            1,
            Math.min(
                basketItem.available_quantity || variant?.stock || 1,
                variant?.stock || basketItem.available_quantity || 1,
            ),
        )
        : Math.max(1, variant?.stock || 1)
    const increaseDisabled = active || !basketItem || basketItem.quantity >= maxQuantity

    if (basketItem) {
        return (
            <View style={[chatScreenStyles.aiSelectedVariantQuantityControl, active ? chatScreenStyles.aiVariantControlDisabled : null]}>
                <Pressable
                    accessibilityRole="button"
                    disabled={active}
                    onPress={(event) => {
                        event.stopPropagation()
                        onQuantityChange(basketItem, basketItem.quantity - 1)
                    }}
                    style={({ pressed }) => [
                        chatScreenStyles.aiSelectedVariantQuantityButton,
                        pressed && !active ? chatScreenStyles.aiSelectedVariantQuantityButtonPressed : null,
                    ]}
                >
                    <Text style={chatScreenStyles.aiSelectedVariantQuantityButtonText}>-</Text>
                </Pressable>

                <View style={chatScreenStyles.aiSelectedVariantQuantityValueWrap}>
                    {active ? (
                        <ActivityIndicator color={colors.onPrimary} size="small" />
                    ) : (
                        <Text numberOfLines={1} style={chatScreenStyles.aiSelectedVariantQuantityValue}>
                            {basketItem.quantity}
                        </Text>
                    )}
                </View>

                <Pressable
                    accessibilityRole="button"
                    disabled={increaseDisabled}
                    onPress={(event) => {
                        event.stopPropagation()
                        onQuantityChange(basketItem, basketItem.quantity + 1)
                    }}
                    style={({ pressed }) => [
                        chatScreenStyles.aiSelectedVariantQuantityButton,
                        increaseDisabled ? chatScreenStyles.aiSelectedVariantQuantityButtonDisabled : null,
                        pressed && !increaseDisabled ? chatScreenStyles.aiSelectedVariantQuantityButtonPressed : null,
                    ]}
                >
                    <Text style={chatScreenStyles.aiSelectedVariantQuantityButtonText}>+</Text>
                </Pressable>
            </View>
        )
    }

    return (
        <Pressable
            accessibilityRole="button"
            disabled={active || isUnavailable}
            onPress={(event) => {
                event.stopPropagation()
                onAdd()
            }}
            style={({ pressed }) => [
                chatScreenStyles.aiSelectedVariantBasketButton,
                (active || isUnavailable) ? chatScreenStyles.aiVariantControlDisabled : null,
                pressed && !(active || isUnavailable) ? chatScreenStyles.aiSelectedVariantBasketButtonPressed : null,
            ]}
        >
            {active ? (
                <ActivityIndicator color={colors.onPrimary} size="small" />
            ) : (
                <Text
                    numberOfLines={1}
                    style={[
                        chatScreenStyles.aiSelectedVariantBasketButtonText,
                        isUnavailable ? chatScreenStyles.aiSelectedVariantBasketButtonTextDisabled : null,
                    ]}
                >
                    {isUnavailable ? "Нет в наличии" : "В корзину"}
                </Text>
            )}
        </Pressable>
    )
}

function AIActionButton({
    action,
    activeActionId,
    containerStyle,
    onPress,
}: {
    action: AIInteractiveAction
    activeActionId: string | null
    containerStyle?: StyleProp<ViewStyle>
    onPress: () => void
}) {
    const busy = activeActionId === action.id
    const disabled = busy || (action.type === "add_to_basket" && !action.action_token && !action.created_basket_item_id)
    const isPrimary = action.style === "primary" && !action.completed

    return (
        <Pressable
            accessibilityRole="button"
            disabled={disabled}
            onPress={(event) => {
                event.stopPropagation()
                onPress()
            }}
            style={({ pressed }) => [
                chatScreenStyles.aiActionButton,
                isPrimary ? chatScreenStyles.aiActionButtonPrimary : chatScreenStyles.aiActionButtonSecondary,
                containerStyle,
                disabled ? chatScreenStyles.aiActionButtonDisabled : null,
                pressed ? chatScreenStyles.aiActionButtonPressed : null,
            ]}
        >
            {busy ? (
                <ActivityIndicator color={colors.onPrimary} size="small" />
            ) : (
                <Text
                    numberOfLines={2}
                    style={[
                        chatScreenStyles.aiActionButtonText,
                        isPrimary ? chatScreenStyles.aiActionButtonPrimaryText : null,
                    ]}
                >
                    {action.label}
                </Text>
            )}
        </Pressable>
    )
}

export function SendActionButton({
    disabled,
    isDark,
    isActive,
    onPress,
    recording,
    sending,
    transcribing,
}: {
    disabled: boolean
    isDark: boolean
    isActive: boolean
    onPress: () => void
    recording: boolean
    sending: boolean
    transcribing: boolean
}) {
    const activeProgress = useRef(new Animated.Value(isActive ? 1 : 0)).current
    const busyProgress = useRef(new Animated.Value(sending || transcribing ? 1 : 0)).current
    const recordingProgress = useRef(new Animated.Value(recording ? 1 : 0)).current

    useEffect(() => {
        Animated.timing(activeProgress, {
            duration: motion.duration.standard,
            easing: motion.easing.standard,
            toValue: isActive ? 1 : 0,
            useNativeDriver: false,
        }).start()
    }, [activeProgress, isActive])

    useEffect(() => {
        Animated.timing(busyProgress, {
            duration: motion.duration.enter,
            easing: motion.easing.standard,
            toValue: sending || transcribing ? 1 : 0,
            useNativeDriver: true,
        }).start()
    }, [busyProgress, sending, transcribing])

    useEffect(() => {
        Animated.timing(recordingProgress, {
            duration: motion.duration.standard,
            easing: motion.easing.standard,
            toValue: recording ? 1 : 0,
            useNativeDriver: false,
        }).start()
    }, [recording, recordingProgress])

    const backgroundColor = activeProgress.interpolate({
        inputRange: [0, 1],
        outputRange: ["rgba(255,255,255,0.94)", "#37C960"],
    })
    const iconOpacity = busyProgress.interpolate({
        inputRange: [0, 1],
        outputRange: [1, 0],
    })
    const spinnerOpacity = busyProgress
    const iconScale = recordingProgress.interpolate({
        inputRange: [0, 1],
        outputRange: [1, 1.08],
    })
    const sendScale = activeProgress.interpolate({
        inputRange: [0, 1],
        outputRange: [1, 1.04],
    })

    return (
        <Pressable
            accessibilityLabel={isActive ? "Send message" : recording ? "Stop voice recording" : "Record voice message"}
            disabled={disabled}
            onPress={onPress}
            style={({ pressed }) => [
                chatScreenStyles.circleButtonPressable,
                pressed && chatScreenStyles.circleButtonPressed,
                disabled && chatScreenStyles.sendButtonDisabled,
            ]}
        >
            <Animated.View
                style={[
                    chatScreenStyles.circleButton,
                    {
                        backgroundColor,
                        transform: [{ scale: isActive ? sendScale : iconScale }],
                    },
                ]}
            >
                <Animated.View
                    pointerEvents="none"
                    style={[
                        chatScreenStyles.sendButtonRecordingLayer,
                        { opacity: recordingProgress },
                    ]}
                />
                <Animated.View style={[chatScreenStyles.sendButtonIconLayer, { opacity: iconOpacity }]}>
                    {isActive ? (
                        <Svg fill="none" height={22} viewBox="0 0 24 24" width={22}>
                            <Path
                                d="M4 20 21 12 4 4l3.5 8L4 20Z"
                                stroke={colors.onPrimary}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.9}
                            />
                        </Svg>
                    ) : (
                        <MicrophoneSvgIcon
                            color={recording ? colors.onPrimary : isDark ? "#E8F0F6" : "#0E0E0E"}
                            height={24}
                            width={24}
                        />
                    )}
                </Animated.View>
                <Animated.View
                    pointerEvents="none"
                    style={[chatScreenStyles.sendButtonSpinnerLayer, { opacity: spinnerOpacity }]}
                >
                    <ActivityIndicator color={isActive ? colors.onPrimary : isDark ? "#E8F0F6" : "#151515"} />
                </Animated.View>
            </Animated.View>
        </Pressable>
    )
}
