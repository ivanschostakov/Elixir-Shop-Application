import { Pressable, View } from "react-native"
import { router } from "expo-router"

import {
    BasketIcon,
    HomeIcon,
    ProfileIcon,
    SavedIcon,
    SearchIcon,
} from "@/components/footer/sticky-footer.icons"
import { stickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { ROUTES } from "@/constants/routes"
import { useBasket } from "@/hooks/basket/use-basket"
import { useLanguage } from "@/providers/language-provider"
import { colors } from "@/theme/colors"

type BottomNavTemplateProps = {
    pathname: string
}

export function BottomNavTemplate({ pathname }: BottomNavTemplateProps) {
    const { basket } = useBasket()
    const { t } = useLanguage()
    const hasBasketItems = (basket?.total_quantity ?? 0) > 0

    const footerItems = [
        {
            accessibilityLabel: t("nav.home"),
            icon: <HomeIcon color={pathname === ROUTES.home ? colors.primary : colors.mutedText} />,
            isActive: pathname === ROUTES.home,
            route: ROUTES.home,
        },
        {
            accessibilityLabel: t("nav.discover"),
            icon: <SearchIcon color={pathname === ROUTES.discover ? colors.primary : colors.mutedText} />,
            isActive: pathname === ROUTES.discover,
            route: ROUTES.discover,
        },
        {
            accessibilityLabel: t("nav.favorites"),
            icon: <SavedIcon color={pathname === ROUTES.favorites ? colors.favorite : colors.mutedText} />,
            isActive: pathname === ROUTES.favorites,
            route: ROUTES.favorites,
        },
        {
            accessibilityLabel: t("nav.basket"),
            icon: (
                <View style={stickyFooterStyles.iconWrap}>
                    <BasketIcon color={pathname === ROUTES.basket ? colors.primary : colors.mutedText} />
                    {hasBasketItems ? <View style={stickyFooterStyles.basketBadge} /> : null}
                </View>
            ),
            isActive: pathname === ROUTES.basket,
            route: ROUTES.basket,
        },
        {
            accessibilityLabel: t("nav.profile"),
            icon: <ProfileIcon color={pathname === ROUTES.profile ? colors.primary : colors.mutedText} />,
            isActive: pathname === ROUTES.profile,
            route: ROUTES.profile,
        },
    ]

    return (
        <View style={stickyFooterStyles.navRow}>
            {footerItems.map((item) => (
                <View key={item.route} style={stickyFooterStyles.footerItem}>
                    <Pressable
                        accessibilityLabel={item.accessibilityLabel}
                        accessibilityRole="button"
                        onPress={() => {
                            if (pathname !== item.route) {
                                router.replace(item.route)
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
