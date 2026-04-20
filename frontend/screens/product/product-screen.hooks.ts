import { createURL } from "expo-linking"
import { useCallback, useEffect, useRef, useState } from "react"
import { Alert, Animated, Share } from "react-native"

import { getProductRoute } from "@/constants/routes"
import {
    getRememberedProductVariantSelection,
    setRememberedProductVariantSelection,
} from "@/hooks/products/product-variant-selection-store"
import type { TranslationFn } from "@/providers/language-provider.types"
import {
    DEFAULT_PRODUCT_INFO_TAB,
} from "@/screens/product/product-screen.constants"
import type {
    ProductInfoTabKey,
    ProductInfoTabLayout,
} from "@/screens/product/product-screen.types"
import { getPreferredVariantId } from "@/screens/product/product-screen.utils"
import type { ProductWithVariantsRead } from "@/types/product"

type UseProductScreenActionsParams = {
    favouriteError: string | null
    isFavourite: boolean
    productId: number
    t: TranslationFn
    toggleFavourite: () => Promise<boolean>
}

export function useSelectedProductVariant(product: ProductWithVariantsRead | null | undefined) {
    const [selectedVariantId, setSelectedVariantId] = useState<number | null>(null)

    useEffect(() => {
        if (!product) {
            setSelectedVariantId(null)
            return
        }

        const rememberedVariantId = getRememberedProductVariantSelection(product.id)?.variantId
        const nextVariantId = getPreferredVariantId(product.variants, rememberedVariantId)

        setSelectedVariantId(nextVariantId)
    }, [product])

    useEffect(() => {
        if (!product) {
            return
        }

        const nextVariant = product.variants.find((variant) => variant.id === selectedVariantId) ?? null

        if (!nextVariant) {
            setRememberedProductVariantSelection(product.id, null)
            return
        }

        setRememberedProductVariantSelection(product.id, {
            stock: nextVariant.stock,
            variantId: nextVariant.id,
        })
    }, [product, selectedVariantId])

    const selectedVariant =
        product?.variants.find((variant) => variant.id === selectedVariantId) ?? product?.variants[0] ?? null

    const handleVariantSelect = useCallback(
        (variantId: number | null) => {
            if (!product || variantId === null) {
                setSelectedVariantId(variantId)
                return
            }

            const nextVariant = product.variants.find((variant) => variant.id === variantId)

            if (!nextVariant || nextVariant.stock === 0) {
                return
            }

            setSelectedVariantId(variantId)
        },
        [product],
    )

    return {
        handleVariantSelect,
        selectedVariant,
        selectedVariantId,
    }
}

export function useProductInfoTabs(productId: number | null) {
    const [activeInfoTab, setActiveInfoTab] = useState<ProductInfoTabKey>(DEFAULT_PRODUCT_INFO_TAB)
    const [tabLayouts, setTabLayouts] = useState<Partial<Record<ProductInfoTabKey, ProductInfoTabLayout>>>({})
    const infoTabIndicatorX = useRef(new Animated.Value(0)).current
    const infoTabIndicatorWidth = useRef(new Animated.Value(0)).current
    const hasMountedInfoTabIndicator = useRef(false)

    useEffect(() => {
        setActiveInfoTab(DEFAULT_PRODUCT_INFO_TAB)
        setTabLayouts({})
        hasMountedInfoTabIndicator.current = false
        infoTabIndicatorX.setValue(0)
        infoTabIndicatorWidth.setValue(0)
    }, [infoTabIndicatorWidth, infoTabIndicatorX, productId])

    useEffect(() => {
        const activeLayout = tabLayouts[activeInfoTab]

        if (!activeLayout) {
            return
        }

        if (!hasMountedInfoTabIndicator.current) {
            infoTabIndicatorX.setValue(activeLayout.x)
            infoTabIndicatorWidth.setValue(activeLayout.width)
            hasMountedInfoTabIndicator.current = true
            return
        }

        Animated.parallel([
            Animated.timing(infoTabIndicatorX, {
                duration: 180,
                toValue: activeLayout.x,
                useNativeDriver: false,
            }),
            Animated.timing(infoTabIndicatorWidth, {
                duration: 180,
                toValue: activeLayout.width,
                useNativeDriver: false,
            }),
        ]).start()
    }, [activeInfoTab, infoTabIndicatorWidth, infoTabIndicatorX, tabLayouts])

    const handleInfoTabLayout = useCallback(
        (tabKey: ProductInfoTabKey, layout: ProductInfoTabLayout) => {
            setTabLayouts((currentLayouts) => {
                const existingLayout = currentLayouts[tabKey]

                if (
                    existingLayout &&
                    existingLayout.width === layout.width &&
                    existingLayout.x === layout.x
                ) {
                    return currentLayouts
                }

                return {
                    ...currentLayouts,
                    [tabKey]: layout,
                }
            })
        },
        [],
    )

    const handleInfoTabChange = useCallback((tabKey: ProductInfoTabKey) => {
        setActiveInfoTab((currentTabKey) => (currentTabKey === tabKey ? currentTabKey : tabKey))
    }, [])

    return {
        activeInfoTab,
        handleInfoTabChange,
        handleInfoTabLayout,
        infoTabIndicatorWidth,
        infoTabIndicatorX,
        showIndicator: Boolean(tabLayouts[activeInfoTab]),
    }
}

export function useProductScreenActions({
    favouriteError,
    isFavourite,
    productId,
    t,
    toggleFavourite,
}: UseProductScreenActionsParams) {
    const handleBookmarkToggle = useCallback(async () => {
        try {
            const nextIsFavourite = await toggleFavourite()
            Alert.alert(nextIsFavourite ? t("product.favoriteAdded") : t("product.favoriteRemoved"))
        } catch (bookmarkError) {
            Alert.alert(
                bookmarkError instanceof Error
                    ? bookmarkError.message
                    : favouriteError ?? t("product.favoriteUpdateFailed"),
            )
        }
    }, [favouriteError, t, toggleFavourite])

    const handleBookmarkPress = useCallback(async () => {
        if (!isFavourite) {
            await handleBookmarkToggle()
            return
        }

        const { showRemoveFavouriteConfirmation } = await import("@/utils/favorites/show-remove-favourite-confirmation")

        showRemoveFavouriteConfirmation(t, () => {
            void handleBookmarkToggle()
        })
    }, [handleBookmarkToggle, isFavourite, t])

    const handleSharePress = useCallback(async () => {
        try {
            const shareUrl = createURL(String(getProductRoute(productId)))

            await Share.share({
                message: `${t("product.shareMessage")}\n${shareUrl}`,
                title: t("route.product"),
                url: shareUrl,
            })
        } catch (shareError) {
            Alert.alert(
                t("product.shareFailedTitle"),
                shareError instanceof Error ? shareError.message : t("product.shareFailedMessage"),
            )
        }
    }, [productId, t])

    return {
        handleBookmarkPress,
        handleSharePress,
    }
}
