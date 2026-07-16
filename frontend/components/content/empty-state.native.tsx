import { Image, Pressable, Text, View } from "react-native"
import LottieView from "lottie-react-native"

import { createContentStyles } from "@/components/content/content.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import type { EmptyStateProps } from "@/components/content/empty-state.types"

export function EmptyState({
    title,
    description,
    eyebrow,
    actionLabel,
    onPressAction,
    sticker,
    illustration,
    variant = "card",
    actionVariant = "button",
}: EmptyStateProps) {
    const contentStyles = useThemeStyles(createContentStyles)
    return (
        <View
            style={[
                contentStyles.emptyState,
                variant === "plain"
                    ? contentStyles.emptyStatePlain
                    : sticker
                        ? contentStyles.emptyStateBorderless
                        : null,
            ]}
        >
            {illustration ? (
                <View style={contentStyles.emptyStateIllustrationWrap}>{illustration}</View>
            ) : sticker ? (
                sticker.kind === "lottie" ? (
                    <LottieView
                        autoPlay
                        loop
                        source={sticker.source}
                        style={[
                            contentStyles.emptyStateIllustration,
                            variant === "plain" && contentStyles.emptyStateIllustrationLarge,
                        ]}
                    />
                ) : (
                    <Image
                        source={sticker.source}
                        style={[
                            contentStyles.emptyStateIllustration,
                            variant === "plain" && contentStyles.emptyStateIllustrationLarge,
                        ]}
                        resizeMode="contain"
                    />
                )
            ) : null}
            {eyebrow ? <Text style={contentStyles.emptyStateEyebrow}>{eyebrow}</Text> : null}
            {title ? <Text style={contentStyles.emptyStateTitle}>{title}</Text> : null}
            {description ? <Text style={contentStyles.emptyStateDescription}>{description}</Text> : null}

            {actionLabel && onPressAction ? (
                <Pressable
                    accessibilityLabel={actionLabel}
                    accessibilityRole="button"
                    onPress={onPressAction}
                    style={({ pressed }) => [
                        actionVariant === "link"
                            ? contentStyles.emptyStateActionLink
                            : contentStyles.emptyStateAction,
                        pressed && contentStyles.emptyStateActionPressed,
                    ]}
                >
                    <Text
                        style={
                            actionVariant === "link"
                                ? contentStyles.emptyStateActionLinkText
                                : contentStyles.emptyStateActionText
                        }
                    >
                        {actionLabel}
                    </Text>
                </Pressable>
            ) : null}
        </View>
    )
}
