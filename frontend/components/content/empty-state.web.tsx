import { Image, Pressable, Text, View, useWindowDimensions } from "react-native"
import { LottieView as WebLottieView } from "lottie-react-native/lib/module/LottieView/index.web"

import {
    getIllustrationSize,
    isLottieSticker,
} from "@/components/content/empty-state.web.const"
import { emptyStateWebStyles, WEB_BREAKPOINTS } from "@/components/content/empty-state.web.styles"
import type { EmptyStateProps } from "@/components/content/empty-state.types"
import { contentStyles } from "@/components/content/content.styles"

function renderSticker(sticker: NonNullable<EmptyStateProps["sticker"]>, illustrationSize: number) {
    return isLottieSticker(sticker) ? (
        <WebLottieView
            autoPlay
            loop
            source={sticker.source}
            style={emptyStateWebStyles.fill}
            webStyle={emptyStateWebStyles.fill}
        />
    ) : (
        <Image
            source={sticker.source}
            style={[
                contentStyles.emptyStateIllustration,
                emptyStateWebStyles.webIllustration,
                { maxWidth: illustrationSize, maxHeight: illustrationSize },
            ]}
            resizeMode="contain"
        />
    )
}

export function EmptyState({
    title,
    description,
    eyebrow,
    actionLabel,
    onPressAction,
    sticker,
    illustration,
}: EmptyStateProps) {
    const { width: windowWidth } = useWindowDimensions()
    const illustrationSize = getIllustrationSize(windowWidth)
    const isDesktop = windowWidth >= WEB_BREAKPOINTS.md

    return (
        <View
            style={[
                contentStyles.emptyState,
                emptyStateWebStyles.webEmptyState,
                isDesktop && emptyStateWebStyles.webEmptyStateDesktop,
                sticker ? contentStyles.emptyStateBorderless : null,
            ]}
        >
            {illustration ? (
                <View
                    style={[
                        contentStyles.emptyStateIllustrationWrap,
                        emptyStateWebStyles.webIllustrationWrap,
                        { width: illustrationSize, height: illustrationSize },
                    ]}
                >
                    {illustration}
                </View>
            ) : sticker ? (
                <View
                    style={[
                        contentStyles.emptyStateIllustrationWrap,
                        emptyStateWebStyles.webIllustrationWrap,
                        { width: illustrationSize, height: illustrationSize },
                    ]}
                >
                    {renderSticker(sticker, illustrationSize)}
                </View>
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
