import { Pressable, View } from "react-native"
import { router } from "expo-router"

import {
    BasketIcon,
    HomeIcon,
    ProfileIcon,
    SavedIcon,
    SearchIcon,
} from "@/components/footer/sticky-footer.icons"
import type { BottomNavTemplateProps } from "@/components/footer/bottom-nav-template.types"
import { stickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { ROUTES } from "@/constants/routes"
import { useBasketDraftEditingId } from "@/hooks/basket/basket-draft-editing-store"
import { useBasket } from "@/hooks/basket/use-basket"
import { useLanguage } from "@/providers/language-provider"
import { colors } from "@/theme/colors"

export function BottomNavTemplate({ pathname }: BottomNavTemplateProps) {
    const { basket } = useBasket()
    const basketDraftEditingId = useBasketDraftEditingId()
    const { t } = useLanguage()
    const hasBasketItems = (basket?.total_quantity ?? 0) > 0
    const basketRoute =
        basketDraftEditingId !== null ? `${ROUTES.basket}?draftId=${basketDraftEditingId}` : ROUTES.basket

    const footerItems = [
        {
            key: ROUTES.home,
            accessibilityLabel: t("nav.home"),
            icon: <HomeIcon color={pathname === ROUTES.home ? colors.primary : colors.mutedText} />,
            isActive: pathname === ROUTES.home,
            route: ROUTES.home,
        },
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
