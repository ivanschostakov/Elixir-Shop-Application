import { Image, Pressable, Text, View } from "react-native"
import LottieView from "lottie-react-native"

import { contentStyles } from "@/components/content/content.styles"
import type { EmptyStateProps } from "@/components/content/empty-state.types"

export function EmptyState({
    title,
    description,
    eyebrow,
    actionLabel,
    onPressAction,
    sticker,
    illustration,
}: EmptyStateProps) {
    return (
        <View
            style={[
                contentStyles.emptyState,
                sticker ? contentStyles.emptyStateBorderless : null,
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
                        style={contentStyles.emptyStateIllustration}
                    />
                ) : (
                    <Image
                        source={sticker.source}
                        style={contentStyles.emptyStateIllustration}
                        resizeMode="contain"
                    />
                )
            ) : null}
            {eyebrow ? <Text style={contentStyles.emptyStateEyebrow}>{eyebrow}</Text> : null}
            <Text style={contentStyles.emptyStateTitle}>{title}</Text>
            <Text style={contentStyles.emptyStateDescription}>{description}</Text>

            {actionLabel && onPressAction ? (
                <Pressable
                    accessibilityLabel={actionLabel}
                    accessibilityRole="button"
                    onPress={onPressAction}
                    style={({ pressed }) => [
                        contentStyles.emptyStateAction,
                        pressed && contentStyles.emptyStateActionPressed,
                    ]}
                >
                    <Text style={contentStyles.emptyStateActionText}>{actionLabel}</Text>
                </Pressable>
            ) : null}
        </View>
    )
}
