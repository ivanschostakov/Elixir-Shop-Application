import { Pressable, View } from "react-native"
import { router } from "expo-router"

import {
    BasketIcon,
    DiscoverIcon,
    HomeIcon,
    ProfileIcon,
    SmileBubbleIcon,
} from "@/components/footer/sticky-footer.icons"
import type { BottomNavTemplateProps } from "@/components/footer/bottom-nav-template.types"
import { createStickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { showAuthRequiredAlert } from "@/components/navigation/auth-required-alert"
import { ROUTES, isAccountRequiredRoute } from "@/constants/routes"
import { useBasketDraftEditingId } from "@/hooks/basket/basket-draft-editing-store"
import { useBasket } from "@/hooks/basket/use-basket"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"

export function BottomNavTemplate({ pathname }: BottomNavTemplateProps) {
    const stickyFooterStyles = useThemeStyles(createStickyFooterStyles)
    const { isAuthenticated } = useAuth()
    const { basket } = useBasket()
    const basketDraftEditingId = useBasketDraftEditingId()
    const { t } = useLanguage()
    const { accentPalette, palette } = useTheme()
    const hasBasketItems = (basket?.total_quantity ?? 0) > 0
    const basketRoute =
        basketDraftEditingId !== null ? `${ROUTES.basket}?draftId=${basketDraftEditingId}` : ROUTES.basket

    const footerItems = [
        {
            key: ROUTES.home,
            accessibilityLabel: t("nav.home"),
            icon: <HomeIcon color={pathname === ROUTES.home ? accentPalette.primary : palette.mutedText} />,
            isActive: pathname === ROUTES.home,
            route: ROUTES.home,
        },
        {
            key: ROUTES.discover,
            accessibilityLabel: t("nav.discover"),
            icon: <DiscoverIcon color={pathname === ROUTES.discover ? accentPalette.primary : palette.mutedText} />,
            isActive: pathname === ROUTES.discover,
            route: ROUTES.discover,
        },
        {
            key: ROUTES.chat,
            accessibilityLabel: t("nav.chat"),
            icon: <SmileBubbleIcon color={pathname === ROUTES.chat ? accentPalette.primary : palette.mutedText} />,
            isActive: pathname === ROUTES.chat,
            route: ROUTES.chat,
        },
        {
            key: ROUTES.basket,
            accessibilityLabel: t("nav.basket"),
            icon: (
                <View style={stickyFooterStyles.iconWrap}>
                    <BasketIcon color={pathname === ROUTES.basket ? accentPalette.primary : palette.mutedText} />
                    {hasBasketItems ? <View style={stickyFooterStyles.basketBadge} /> : null}
                </View>
            ),
            isActive: pathname === ROUTES.basket,
            route: basketRoute,
        },
        {
            key: ROUTES.profile,
            accessibilityLabel: t("nav.profile"),
            icon: <ProfileIcon color={pathname === ROUTES.profile ? accentPalette.primary : palette.mutedText} />,
            isActive: pathname === ROUTES.profile,
            route: ROUTES.profile,
        },
    ]

    return (
        <View style={stickyFooterStyles.navRow}>
            {footerItems.map((item) => (
                <View key={item.key} style={stickyFooterStyles.footerItem}>
                    <Pressable
                        accessibilityLabel={item.accessibilityLabel}
                        accessibilityRole="button"
                        onPress={() => {
                            if (!item.isActive) {
                                if (!isAuthenticated && isAccountRequiredRoute(item.route)) {
                                    showAuthRequiredAlert({
                                        onLogin: () => {
                                            router.push(ROUTES.login)
                                        },
                                    })
                                    return
                                }

                                router.replace(item.route as never)
                            }
                        }}
                        style={({ pressed }) => [
                            stickyFooterStyles.iconButton,
                            item.isActive && pressed && stickyFooterStyles.iconButtonPressed,
                        ]}
                    >
                        {item.icon}
                    </Pressable>
                </View>
            ))}
        </View>
    )
}
