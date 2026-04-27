import { ActivityIndicator, View } from "react-native"
import { router } from "expo-router"
import type { ReactNode } from "react"

import { ContentRail } from "@/components/content/content-rail"
import { RecentOrderDraftsRail } from "@/components/content/recent-order-drafts-rail"
import { FeedTemplate } from "@/components/templates/feed-template"
import { useRecommendations } from "@/hooks/recommendations/use-recommendations"
import { ROUTES } from "@/constants/routes"
import { useRecentOrderDrafts } from "@/hooks/order-draft/use-recent-order-drafts"
import { useLatestProducts } from "@/hooks/products/use-latest-products"
import { useLanguage } from "@/providers/language-provider"
import { colors } from "@/theme/colors"
import { homeScreenStyles } from "./home-screen.styles"

export default function HomeScreen() {
    const { t } = useLanguage()
    const { products: latestProducts, loading: latestLoading } = useLatestProducts(9)
    const { products: recommendedProducts, loading: recommendedLoading } = useRecommendations({
        surface: "home",
        limit: 8,
    })
    const { orderDrafts: recentOrderDrafts, loading: recentOrderDraftsLoading } = useRecentOrderDrafts(6)

    const sections: { key: string, content: ReactNode }[] = []

    if (latestProducts.length) {
        sections.push({
            key: "latest",
            content: (
                <ContentRail
                    title={t("home.newInTitle")}
                    eyebrow={t("home.newInEyebrow")}
                    description={t("home.newInDescription")}
                    actionLabel={t("common.viewAll")}
                    onPressAction={() => router.push(ROUTES.discover)}
                    products={latestProducts}
                />
            ),
        })
    } else if (latestLoading) {
        sections.push({
            key: "latest-loading",
            content: (
                <View style={homeScreenStyles.loadingWrap}>
                    <ActivityIndicator color={colors.primary} />
                </View>
            ),
        })
    }

    if (recentOrderDrafts.length) {
        sections.push({
            key: "recent-drafts",
            content: <RecentOrderDraftsRail drafts={recentOrderDrafts} />,
        })
    } else if (recentOrderDraftsLoading) {
        sections.push({
            key: "recent-drafts-loading",
            content: (
                <View style={homeScreenStyles.loadingWrap}>
                    <ActivityIndicator color={colors.primary} />
                </View>
            ),
        })
    }

    if (recommendedProducts.length) {
        sections.push({
            key: "recommended",
            content: (
                <ContentRail
                    title={t("home.recommendedTitle")}
                    eyebrow={t("home.recommendedEyebrow")}
                    description={t("home.recommendedDescription")}
                    products={recommendedProducts}
                />
            ),
        })
    } else if (recommendedLoading) {
        sections.push({
            key: "recommended-loading",
            content: (
                <View style={homeScreenStyles.loadingWrap}>
                    <ActivityIndicator color={colors.primary} />
                </View>
            ),
        })
    }

    return (
        <FeedTemplate
            contentContainerStyle={homeScreenStyles.content}
            scrollViewStyle={homeScreenStyles.container}
        >
            {sections.map((section, index) => {
                const isFirst = index === 0
                const isLast = index === sections.length - 1

                return (
                    <View
                        key={section.key}
                        style={[
                            homeScreenStyles.sectionBlock,
                            isFirst && homeScreenStyles.sectionBlockTop,
                            isLast && homeScreenStyles.sectionBlockBottom,
                        ]}
                    >
                        {section.content}
                    </View>
                )
            })}
        </FeedTemplate>
    )
}
