import { ActivityIndicator, View } from "react-native"

import ImageCarousel from "@/components/image-carousel/image-carousel"
import { createContentStyles } from "@/components/content/content.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"
import { ProductCard } from "@/components/content/product-card"
import { SectionHeader } from "@/components/content/section-header"
import type { ContentRailProps } from "@/components/content/content-rail.types"
import type { ProductWithVariantsRead } from "@/types/product"

export function ContentRail({
    title,
    eyebrow,
    description,
    actionLabel,
    onPressAction,
    products,
    layout = "carousel",
    gridVariant = "default",
    mergeHeaderWithFirstRow = false,
    carouselEdgeInset,
    loadingMore = false,
}: ContentRailProps) {
    const contentStyles = useThemeStyles(createContentStyles)
    const { palette } = useTheme()
    if (!products.length) {
        return null
    }

    const discoverRows = gridVariant === "discover"
        ? products.reduce<ProductWithVariantsRead[][]>((rows, product, index) => {
              if (index % 2 === 0) {
                  rows.push([product])
              } else {
                  rows[rows.length - 1]?.push(product)
              }
              return rows
          }, [])
        : []
    const firstDiscoverRow = mergeHeaderWithFirstRow ? discoverRows[0] ?? null : null
    const remainingDiscoverRows = mergeHeaderWithFirstRow ? discoverRows.slice(1) : discoverRows
    const headerNode = (
        <SectionHeader
            title={title}
            eyebrow={eyebrow}
            description={description}
            actionLabel={actionLabel}
            onPressAction={onPressAction}
        />
    )

    return (
        <View style={contentStyles.railSection} testID="product-rail">
            {!(layout === "grid" && gridVariant === "discover" && mergeHeaderWithFirstRow) ? headerNode : null}

            {layout === "grid" ? (
                <>
                    {gridVariant === "discover" ? (
                        <View style={contentStyles.railGridDiscover}>
                            {firstDiscoverRow ? (
                                <View style={contentStyles.railGridDiscoverMergedCard}>
                                    <View style={contentStyles.railGridDiscoverMergedHeader}>
                                        {headerNode}
                                    </View>
                                    <View
                                        style={[
                                            contentStyles.railGridDiscoverRow,
                                            contentStyles.railGridDiscoverMergedFirstRow,
                                        ]}
                                    >
                                        {firstDiscoverRow.map((product) => (
                                            <View
                                                key={product.id}
                                                style={contentStyles.railGridDiscoverItem}
                                            >
                                                <ProductCard
                                                    product={product}
                                                    style={contentStyles.railGridDiscoverCard}
                                                />
                                            </View>
                                        ))}
                                        {firstDiscoverRow.length === 1 ? (
                                            <View style={contentStyles.railGridDiscoverSpacer} />
                                        ) : null}
                                    </View>
                                </View>
                            ) : null}
                            {remainingDiscoverRows.map((row, rowIndex) => (
                                <View
                                    key={`${title}-${firstDiscoverRow ? rowIndex + 1 : rowIndex}`}
                                    style={contentStyles.railGridDiscoverRow}
                                >
                                    {row.map((product) => (
                                        <View
                                            key={product.id}
                                            style={contentStyles.railGridDiscoverItem}
                                        >
                                            <ProductCard
                                                product={product}
                                                style={contentStyles.railGridDiscoverCard}
                                            />
                                        </View>
                                    ))}
                                    {row.length === 1 ? (
                                        <View style={contentStyles.railGridDiscoverSpacer} />
                                    ) : null}
                                </View>
                            ))}
                        </View>
                    ) : (
                        <View style={contentStyles.railGrid}>
                            {products.map((product) => (
                                <View key={product.id} style={contentStyles.railGridItem}>
                                    <ProductCard product={product} />
                                </View>
                            ))}
                        </View>
                    )}

                    {loadingMore ? (
                        <View style={contentStyles.railLoaderWrap}>
                            <ActivityIndicator color={palette.primary} />
                        </View>
                    ) : null}
                </>
            ) : (
                <ImageCarousel products={products} edgeInset={carouselEdgeInset} />
            )}
        </View>
    )
}
