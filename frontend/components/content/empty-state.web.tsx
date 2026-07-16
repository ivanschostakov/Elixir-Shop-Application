import { Pressable, Text, View, useWindowDimensions } from "react-native"

import {
    getIllustrationSize,
} from "@/components/content/empty-state.web.const"
import { renderSticker } from "@/components/content/empty-state.web.utils"
import { emptyStateWebStyles, WEB_BREAKPOINTS } from "@/components/content/empty-state.web.styles"
import type { EmptyStateProps } from "@/components/content/empty-state.types"
import { createContentStyles } from "@/components/content/content.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"

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
    const { width: windowWidth } = useWindowDimensions()
    const illustrationSize = variant === "plain"
        ? Math.max(getIllustrationSize(windowWidth), 180)
        : getIllustrationSize(windowWidth)
    const isDesktop = windowWidth >= WEB_BREAKPOINTS.md

    return (
        <View
            style={[
                contentStyles.emptyState,
                emptyStateWebStyles.webEmptyState,
                isDesktop && variant !== "plain" && emptyStateWebStyles.webEmptyStateDesktop,
                variant === "plain"
                    ? contentStyles.emptyStatePlain
                    : sticker
                        ? contentStyles.emptyStateBorderless
                        : null,
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
                    {renderSticker(sticker, illustrationSize, contentStyles.emptyStateIllustration)}
                </View>
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
