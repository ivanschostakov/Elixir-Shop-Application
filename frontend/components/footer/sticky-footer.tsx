import { Animated, KeyboardAvoidingView, Platform, View } from "react-native"
import { usePathname } from "expo-router"
import { SafeAreaView } from "react-native-safe-area-context"

import { BottomActionTemplate } from "@/components/footer/bottom-action-template"
import { BottomNavTemplate } from "@/components/footer/bottom-nav-template"
import { stickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import type {
    StickyFooterProps,
    StickyFooterSurfaceProps,
} from "@/components/footer/sticky-footer.types"
import { useEntranceAnimation } from "@/hooks/animation/use-entrance-animation"
import { useBasket } from "@/hooks/basket/use-basket"

export function StickyFooterSurface({
    children,
    contentStyle,
    style,
    variant = "default",
}: StickyFooterSurfaceProps) {
    const entranceStyle = useEntranceAnimation({ translateY: 10 })

    return (
        <Animated.View style={entranceStyle}>
            <SafeAreaView
                edges={["bottom"]}
                style={[
                    stickyFooterStyles.footerBase,
                    stickyFooterStyles.elevatedSurface,
                    style,
                ]}
            >
                <View
                    style={[
                        variant === "search"
                            ? stickyFooterStyles.searchSection
                            : stickyFooterStyles.actionSection,
                        contentStyle,
                    ]}
                >
                    {children}
                </View>
            </SafeAreaView>
        </Animated.View>
    )
}

export default function StickyFooter({ template }: StickyFooterProps) {
    const pathname = usePathname()
    const { basket } = useBasket()
    const entranceStyle = useEntranceAnimation({ translateY: 10 })
    const hasBasketItems = (basket?.total_quantity ?? 0) > 0
    const showProductAction = template.footer === "nav+productAction"
    const showBasketAction = template.footer === "nav+basketAction" && hasBasketItems
    const showCustomAction = template.footer === "nav+customAction" && Boolean(template.slots?.footer)

    if (template.footer === "customSurface") {
        return template.slots?.footer ? <StickyFooterSurface>{template.slots.footer}</StickyFooterSurface> : null
    }

    if (showProductAction || showBasketAction || showCustomAction) {
        return (
            <Animated.View style={[stickyFooterStyles.footerBase, stickyFooterStyles.elevatedSurface, entranceStyle]}>
                <View style={stickyFooterStyles.stack}>
                    <KeyboardAvoidingView
                        behavior={Platform.OS === "ios" ? "padding" : "height"}
                        keyboardVerticalOffset={0}
                        style={stickyFooterStyles.actionKeyboardLayer}
                    >
                        <View style={stickyFooterStyles.actionSection}>
                            {showCustomAction
                                ? template.slots?.footer
                                : <BottomActionTemplate variant={showProductAction ? "product" : "basket"} />}
                        </View>
                    </KeyboardAvoidingView>
                    <BottomNavTemplate pathname={pathname} />
                </View>
            </Animated.View>
        )
    }

    return (
        <Animated.View style={[stickyFooterStyles.footerBase, entranceStyle]}>
            <BottomNavTemplate pathname={pathname} />
        </Animated.View>
    )
}
