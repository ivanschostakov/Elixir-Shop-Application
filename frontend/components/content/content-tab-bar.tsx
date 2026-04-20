import { Pressable, Text, View } from "react-native"

import { contentStyles } from "@/components/content/content.styles"
import type { ContentTabBarProps } from "@/components/content/content-tab-bar.types"
export type { ContentTabBarItem } from "@/components/content/content-tab-bar.types"

export function ContentTabBar({ tabs }: ContentTabBarProps) {
    return (
        <View style={contentStyles.topTabBar}>
            {tabs.map((tab) => (
                <Pressable
                    key={tab.key}
                    accessibilityRole="button"
                    accessibilityState={{ selected: tab.isActive }}
                    onPress={tab.onPress}
                    style={({ pressed }) => [
                        contentStyles.topTabButton,
                        tab.isActive && contentStyles.topTabButtonActive,
                        pressed && contentStyles.topTabButtonPressed,
                    ]}
                >
                    <Text
                        style={[
                            contentStyles.topTabLabel,
                            tab.isActive && contentStyles.topTabLabelActive,
                        ]}
                    >
                        {tab.label}
                    </Text>
                </Pressable>
            ))}
        </View>
    )
}
