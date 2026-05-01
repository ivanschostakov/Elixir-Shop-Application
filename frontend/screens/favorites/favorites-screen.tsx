import { ActivityIndicator, Alert, FlatList, ScrollView, View } from "react-native"
import { useLocalSearchParams, useRouter } from "expo-router"

import { EmptyState } from "@/components/content/empty-state"
import { CatalogTemplate } from "@/components/templates/catalog-template"
import { ROUTES } from "@/constants/routes"
import { STICKERS } from "@/constants/stickers"
import { useFavouriteProducts } from "@/hooks/favorites/use-favourite-products"
import { resolveContentTab } from "@/hooks/navigation/use-content-tabs"
import { useLanguage } from "@/providers/language-provider"
import { FavoriteProductItem } from "@/screens/favorites/favorite-product-item"
import { favoritesScreenStyles } from "@/screens/favorites/favorites-screen.styles"
import { colors } from "@/theme/colors"
import { showRemoveFavouriteConfirmation } from "@/utils/favorites/show-remove-favourite-confirmation"

export default function FavoritesScreen() {
    const router = useRouter()
    const { t } = useLanguage()
    const params = useLocalSearchParams<{ tab?: string | string[] }>()
    const {
        error,
        loading,
        products,
        refresh,
        refreshing,
        removeFavourite,
        removingProductId,
    } = useFavouriteProducts()
    const isProductsTab = resolveContentTab(params.tab) === "products"
    const savedProducts = isProductsTab ? products : []

    const handleRemoveFavourite = async (productId: number) => {
        showRemoveFavouriteConfirmation(t, () => {
            void (async () => {
                try {
                    await removeFavourite(productId)
                } catch (err) {
                    Alert.alert(
                        t("favorites.removeFailedTitle"),
                        err instanceof Error ? err.message : t("favorites.removeFailedMessage"),
                    )
                }
            })()
        })
    }

    if (!isProductsTab) {
        return (
            <CatalogTemplate style={favoritesScreenStyles.screen}>
                <View style={favoritesScreenStyles.emptyContent}>
                    <EmptyState
                        actionVariant="link"
                        sticker={STICKERS.noArticles}
                        description={t("favorites.articlesEmptyDescription")}
                        actionLabel={t("favorites.openCatalog")}
                        onPressAction={() => router.push(ROUTES.discover)}
                        variant="plain"
                    />
                </View>
            </CatalogTemplate>
        )
    }

    if (loading && !products.length) {
        return (
            <CatalogTemplate style={favoritesScreenStyles.screen}>
                <ScrollView
                    contentContainerStyle={favoritesScreenStyles.stateContent}
                    showsVerticalScrollIndicator={false}
                >
                    <View style={favoritesScreenStyles.loaderWrap}>
                        <ActivityIndicator color={colors.primary} />
                    </View>
                </ScrollView>
            </CatalogTemplate>
        )
    }

    if (error && !products.length) {
        return (
            <CatalogTemplate style={favoritesScreenStyles.screen}>
                <ScrollView
                    contentContainerStyle={favoritesScreenStyles.stateContent}
                    showsVerticalScrollIndicator={false}
                >
                    <EmptyState
                        eyebrow={t("favorites.productsTab")}
                        title={t("favorites.loadFailedMessage")}
                        description={error || t("favorites.loadFailedMessage")}
                        actionLabel={t("favorites.retry")}
                        onPressAction={() => void refresh()}
                    />
                </ScrollView>
            </CatalogTemplate>
        )
    }

    if (!products.length) {
        return (
            <CatalogTemplate style={favoritesScreenStyles.emptyContainer}>
                <View style={favoritesScreenStyles.emptyContent}>
                    <EmptyState
                        actionVariant="link"
                        sticker={STICKERS.favoritesEmpty}
                        description={t("favorites.emptyDescription")}
                        actionLabel={t("favorites.openCatalog")}
                        onPressAction={() => router.push(ROUTES.discover)}
                        variant="plain"
                    />
                </View>
            </CatalogTemplate>
        )
    }

    return (
        <CatalogTemplate style={favoritesScreenStyles.screen}>
            <FlatList
                data={savedProducts}
                keyExtractor={(product) => String(product.id)}
                contentContainerStyle={favoritesScreenStyles.listContent}
                ItemSeparatorComponent={() => <View style={favoritesScreenStyles.separator} />}
                onRefresh={() => void refresh()}
                refreshing={refreshing}
                renderItem={({ item }) => {
                    const isRemoving = removingProductId === item.id

                    return (
                        <FavoriteProductItem
                            isRemoving={isRemoving}
                            onRemove={handleRemoveFavourite}
                            product={item}
                        />
                    )
                }}
            />
        </CatalogTemplate>
    )
}
