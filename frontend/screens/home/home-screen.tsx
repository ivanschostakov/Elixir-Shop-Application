import { ActivityIndicator, View } from "react-native"
import { router } from "expo-router"

import { ContentRail } from "@/components/content/content-rail"
import { FeedTemplate } from "@/components/templates/feed-template"
import { ROUTES } from "@/constants/routes"
import { useFavouriteProducts } from "@/hooks/favorites/use-favourite-products"
import { useLatestProducts } from "@/hooks/products/use-latest-products"
import { usePriorityProducts } from "@/hooks/products/use-priority-products"
import { useLanguage } from "@/providers/language-provider"
import { colors } from "@/theme/colors"
import { homeScreenStyles } from "./home-screen.styles"

export default function HomeScreen() {
    const { t } = useLanguage()
    const { products: latestProducts, loading: latestLoading } = useLatestProducts(9)
    const { products: priorityProducts, loading: recommendedLoading } = usePriorityProducts(4)
    const { products: favouriteProducts, loading: favouritesLoading } = useFavouriteProducts()

    return (
        <FeedTemplate
            contentContainerStyle={homeScreenStyles.content}
            scrollViewStyle={homeScreenStyles.container}
        >
            {latestProducts.length ? (
                <ContentRail
                    title={t("home.newInTitle")}
                    eyebrow={t("home.newInEyebrow")}
                    description={t("home.newInDescription")}
                    actionLabel={t("common.viewAll")}
                    onPressAction={() => router.push(ROUTES.discover)}
                    products={latestProducts}
                />
            ) : latestLoading ? (
                <View style={homeScreenStyles.loadingWrap}>
                    <ActivityIndicator color={colors.primary} />
                </View>
            ) : null}

            {!favouritesLoading && favouriteProducts.length ? (
                <ContentRail
                    title={t("home.savedTitle")}
                    eyebrow={t("home.savedEyebrow")}
                    description={t("home.savedDescription")}
                    actionLabel={t("common.viewAll")}
                    onPressAction={() => router.push(ROUTES.favorites)}
                    products={favouriteProducts}
                />
            ) : null}

            {priorityProducts.length ? (
                <ContentRail
                    title={t("home.recommendedTitle")}
                    eyebrow={t("home.recommendedEyebrow")}
                    description={t("home.recommendedDescription")}
                    products={priorityProducts}
                />
            ) : recommendedLoading ? (
                <View style={homeScreenStyles.loadingWrap}>
                    <ActivityIndicator color={colors.primary} />
                </View>
            ) : null}
        </FeedTemplate>
    )
}
