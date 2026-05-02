import { useEffect, useState } from "react"
import { Alert, Animated, Pressable, Text, View, useWindowDimensions } from "react-native"
import { BlurView } from "expo-blur"
import { usePathname, useRouter } from "expo-router"
import { Path, Svg } from "react-native-svg"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { ContentTabBar } from "@/components/content/content-tab-bar"
import { HeaderMenu } from "@/components/header/header-menu"
import { HeaderSearchPanel } from "@/components/header/header-search-panel"
import type { AppHeaderProps } from "@/components/header/app-header.types"
import {
    BACK_ARROW_PATH,
    CLEAR_ICON_PATH,
    CLOSE_ICON_PATH,
    SEARCH_BACKDROP_BLUR_INTENSITY,
    SEARCH_ICON_PATH,
} from "@/components/header/app-header.constants"
import { getHeaderStyles } from "@/components/header/app-header.styles"
import { ROUTES, isPrimaryAppRoute } from "@/constants/routes"
import { useEntranceAnimation } from "@/hooks/animation/use-entrance-animation"
import { useBasket } from "@/hooks/basket/use-basket"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import { useContentTabs } from "@/hooks/navigation/use-content-tabs"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { colors } from "@/theme/colors"

export default function AppHeader({ template }: AppHeaderProps) {
    const pathname = usePathname()
    const router = useRouter()
    const topInset = useSafeAreaInsets().top
    const { height: windowHeight } = useWindowDimensions()
    const styles = getHeaderStyles(topInset, windowHeight)
    const { isDark, themeName, toggleTheme } = useTheme()
    const { signOut } = useAuth()
    const { basket } = useBasket()
    const { clear, error: basketError, updating: basketUpdating } = useBasketMutations()
    const { t } = useLanguage()
    const { tabs } = useContentTabs(pathname, {
        articles: t("common.articles"),
        products: t("common.products"),
    })
    const entranceStyle = useEntranceAnimation({ translateY: -6 })
    const [isMenuOpen, setIsMenuOpen] = useState(false)
    const [isSearchMode, setIsSearchMode] = useState(false)
    const headerVariant = template.header
    const title = template.title ?? ""
    const showBackButton = !isPrimaryAppRoute(pathname)
    const canToggleSearch = headerVariant === "search" || (headerVariant === "tabs" && pathname === ROUTES.discover)
    const isBasketPage = pathname === ROUTES.basket
    const hasBasketItems = (basket?.items_count ?? 0) > 0

    useEffect(() => {
        setIsMenuOpen(false)
        setIsSearchMode(false)
    }, [pathname])

    useEffect(() => {
        if (!canToggleSearch) {
            setIsSearchMode(false)
        }
    }, [canToggleSearch])

    const handleSearchToggle = () => {
        if (!canToggleSearch) {
            return
        }

        setIsMenuOpen(false)
        setIsSearchMode((currentValue) => !currentValue)
    }

    const handleClearBasket = () => {
        Alert.alert(
            t("cart.clearConfirmTitle"),
            t("cart.clearConfirmMessage"),
            [
                {
                    style: "cancel",
                    text: t("common.cancel"),
                },
                {
                    onPress: () => {
                        void clear().catch((error) => {
                            Alert.alert(
                                error instanceof Error ? error.message : basketError ?? t("cart.updateFailed"),
                            )
                        })
                    },
                    style: "destructive",
                    text: t("cart.clearCta"),
                },
            ],
        )
    }

    const renderLeftSlot = () => {
        if (template.slots?.headerLeft) {
            return template.slots.headerLeft
        }

        if (showBackButton) {
            return (
                <Pressable
                    accessibilityLabel={t("nav.back")}
                    accessibilityRole="button"
                    onPress={() => (router.canGoBack() ? router.back() : router.push(ROUTES.discover))}
                    style={({ pressed }) => [styles.sideButton, pressed && styles.sideButtonPressed]}
                    hitSlop={12}
                >
                    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                        <Path d={BACK_ARROW_PATH} fill={colors.primary} />
                    </Svg>
                </Pressable>
            )
        }

        if (canToggleSearch) {
            return (
                <Pressable
                    accessibilityLabel={isSearchMode ? t("nav.closeSearch") : t("nav.search")}
                    accessibilityRole="button"
                    onPress={handleSearchToggle}
                    style={({ pressed }) => [styles.sideButton, pressed && styles.sideButtonPressed]}
                    hitSlop={12}
                >
                    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                        <Path d={isSearchMode ? CLOSE_ICON_PATH : SEARCH_ICON_PATH} fill={colors.primary} />
                    </Svg>
                </Pressable>
            )
        }

        return <View style={styles.sideSlot} />
    }

    const renderDefaultRightSlot = () => {
        if (isBasketPage && hasBasketItems) {
            return (
                <Pressable
                    accessibilityLabel={t("cart.clearCta")}
                    accessibilityRole="button"
                    disabled={basketUpdating}
                    onPress={handleClearBasket}
                    style={({ pressed }) => [
                        styles.headerActionButton,
                        basketUpdating && styles.headerActionButtonDisabled,
                        pressed && styles.menuButtonPressed,
                    ]}
                    hitSlop={12}
                >
                    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                        <Path
                            d={CLEAR_ICON_PATH}
                            stroke={colors.primary}
                            strokeWidth={2}
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        />
                    </Svg>
                </Pressable>
            )
        }

        return (
            <HeaderMenu
                isOpen={isMenuOpen}
                onClose={() => setIsMenuOpen(false)}
                onOpenContacts={() => {
                    setIsMenuOpen(false)
                    router.push(ROUTES.contacts)
                }}
                onOpenPublicOffer={() => {
                    setIsMenuOpen(false)
                    router.push(ROUTES.publicOffer)
                }}
                onOpenRequisites={() => {
                    setIsMenuOpen(false)
                    router.push(ROUTES.requisites)
                }}
                onSignOut={signOut}
                onToggleTheme={toggleTheme}
                onToggle={() => setIsMenuOpen((currentValue) => !currentValue)}
                styles={styles}
                t={t}
                themeName={themeName}
            />
        )
    }

    const renderCenterSlot = () => {
        if (isSearchMode) {
            return (
                <HeaderSearchPanel
                    onClose={() => setIsSearchMode(false)}
                    pathname={pathname}
                    styles={styles}
                    t={t}
                    visible={isSearchMode}
                />
            )
        }

        if (template.slots?.headerCenter) {
            return template.slots.headerCenter
        }

        if (headerVariant === "tabs") {
            return (
                <View style={styles.centerSlotContent}>
                    <ContentTabBar tabs={tabs} />
                </View>
            )
        }

        return (
            <Text numberOfLines={1} style={styles.title}>
                {title}
            </Text>
        )
    }

    return (
        <Animated.View style={[styles.wrapper, headerVariant === "overlay" && styles.wrapperOverlay, entranceStyle]}>
            {isSearchMode ? (
                <Pressable
                    accessibilityLabel={t("nav.closeSearch")}
                    accessibilityRole="button"
                    onPress={handleSearchToggle}
                    style={styles.searchBackdrop}
                >
                    <BlurView
                        intensity={SEARCH_BACKDROP_BLUR_INTENSITY}
                        style={styles.searchBackdropBlur}
                        tint={isDark ? "dark" : "light"}
                    />
                </Pressable>
            ) : null}

            <View style={styles.content}>
                <View style={styles.leftSlot}>{renderLeftSlot()}</View>

                <View style={styles.centerSlot}>{renderCenterSlot()}</View>

                <View style={styles.rightSlot}>{template.slots?.headerRight ?? renderDefaultRightSlot()}</View>
            </View>
        </Animated.View>
    )
}
