import { Pressable, View } from "react-native"
import { router } from "expo-router"

import {
    BasketIcon,
    ProfileIcon,
    SavedIcon,
    SearchIcon,
    SmileBubbleIcon,
} from "@/components/footer/sticky-footer.icons"
import type { BottomNavTemplateProps } from "@/components/footer/bottom-nav-template.types"
import { stickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { showAuthRequiredAlert } from "@/components/navigation/auth-required-alert"
import { ROUTES, isAccountRequiredRoute } from "@/constants/routes"
import { useBasketDraftEditingId } from "@/hooks/basket/basket-draft-editing-store"
import { useBasket } from "@/hooks/basket/use-basket"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { colors } from "@/theme/colors"

export function BottomNavTemplate({ pathname }: BottomNavTemplateProps) {
    const { isAuthenticated } = useAuth()
    const { basket } = useBasket()
    const basketDraftEditingId = useBasketDraftEditingId()
    const { t } = useLanguage()
    const hasBasketItems = (basket?.total_quantity ?? 0) > 0
    const basketRoute =
        basketDraftEditingId !== null ? `${ROUTES.basket}?draftId=${basketDraftEditingId}` : ROUTES.basket

    const footerItems = [
        {
            key: ROUTES.discover,
            accessibilityLabel: t("nav.discover"),
            icon: <SearchIcon color={pathname === ROUTES.discover ? colors.primary : colors.mutedText} />,
            isActive: pathname === ROUTES.discover,
            route: ROUTES.discover,
        },
        {
            key: ROUTES.favorites,
            accessibilityLabel: t("nav.favorites"),
            icon: <SavedIcon color={pathname === ROUTES.favorites ? colors.favorite : colors.mutedText} />,
            isActive: pathname === ROUTES.favorites,
            route: ROUTES.favorites,
        },
        {
            key: ROUTES.chat,
            accessibilityLabel: t("nav.chat"),
            icon: <SmileBubbleIcon color={pathname === ROUTES.chat ? colors.primary : colors.mutedText} />,
            isActive: pathname === ROUTES.chat,
            route: ROUTES.chat,
        },
        {
            key: ROUTES.basket,
            accessibilityLabel: t("nav.basket"),
            icon: (
                <View style={stickyFooterStyles.iconWrap}>
                    <BasketIcon color={pathname === ROUTES.basket ? colors.primary : colors.mutedText} />
                    {hasBasketItems ? <View style={stickyFooterStyles.basketBadge} /> : null}
                </View>
            ),
            isActive: pathname === ROUTES.basket,
            route: basketRoute,
        },
        {
            key: ROUTES.profile,
            accessibilityLabel: t("nav.profile"),
            icon: <ProfileIcon color={pathname === ROUTES.profile ? colors.primary : colors.mutedText} />,
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
