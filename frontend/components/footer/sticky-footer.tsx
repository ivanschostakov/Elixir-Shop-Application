import { View } from "react-native"
import { usePathname } from "expo-router"
import { SafeAreaView } from "react-native-safe-area-context"

import { BottomActionTemplate } from "@/components/footer/bottom-action-template"
import { BottomNavTemplate } from "@/components/footer/bottom-nav-template"
import { stickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import type {
    StickyFooterProps,
    StickyFooterSurfaceProps,
} from "@/components/footer/sticky-footer.types"
import { useBasket } from "@/hooks/basket/use-basket"

export function StickyFooterSurface({
    children,
    contentStyle,
    style,
    variant = "default",
}: StickyFooterSurfaceProps) {
    return (
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
    )
}

export default function StickyFooter({ template }: StickyFooterProps) {
    const pathname = usePathname()
    const { basket } = useBasket()
    const hasBasketItems = (basket?.total_quantity ?? 0) > 0
    const showProductAction = template.footer === "nav+productAction"
    const showBasketAction = template.footer === "nav+basketAction" && hasBasketItems

    if (template.footer === "customSurface") {
        return template.slots?.footer ? <StickyFooterSurface>{template.slots.footer}</StickyFooterSurface> : null
    }

    if (showProductAction || showBasketAction) {
        return (
            <View style={[stickyFooterStyles.footerBase, stickyFooterStyles.elevatedSurface]}>
                <View style={stickyFooterStyles.stack}>
                    <View style={stickyFooterStyles.actionSection}>
                        <BottomActionTemplate variant={showProductAction ? "product" : "basket"} />
                    </View>
                    <BottomNavTemplate pathname={pathname} />
                </View>
            </View>
        )
    }

    return (
        <View style={stickyFooterStyles.footerBase}>
            <BottomNavTemplate pathname={pathname} />
        </View>
    )
}
