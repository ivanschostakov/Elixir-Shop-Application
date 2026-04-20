import { Pressable, Text, View } from "react-native"

import { contentStyles } from "@/components/content/content.styles"
import type { SectionHeaderProps } from "@/components/content/section-header.types"

export function SectionHeader({
    title,
    eyebrow,
    description,
    actionLabel,
    onPressAction,
}: SectionHeaderProps) {
    return (
        <View style={contentStyles.sectionHeader}>
            <View style={contentStyles.sectionHeaderCopy}>
                {eyebrow ? <Text style={contentStyles.sectionEyebrow}>{eyebrow}</Text> : null}
                <Text style={contentStyles.sectionTitle}>{title}</Text>
                {description ? (
                    <Text style={contentStyles.sectionDescription}>{description}</Text>
                ) : null}
            </View>

            {actionLabel && onPressAction ? (
                <Pressable
                    accessibilityLabel={actionLabel}
                    accessibilityRole="button"
                    onPress={onPressAction}
                    style={({ pressed }) => [
                        contentStyles.sectionAction,
                        pressed && contentStyles.sectionActionPressed,
                    ]}
                >
                    <Text style={contentStyles.sectionActionText}>{actionLabel}</Text>
                </Pressable>
            ) : null}
        </View>
    )
}
