import { Pressable, Text, View, useWindowDimensions } from "react-native"

import {
    getIllustrationSize,
} from "@/components/content/empty-state.web.const"
import { renderSticker } from "@/components/content/empty-state.web.utils"
import { emptyStateWebStyles, WEB_BREAKPOINTS } from "@/components/content/empty-state.web.styles"
import type { EmptyStateProps } from "@/components/content/empty-state.types"
import { contentStyles } from "@/components/content/content.styles"

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
