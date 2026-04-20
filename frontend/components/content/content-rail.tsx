import { View } from "react-native"

import ImageCarousel from "@/components/image-carousel/image-carousel"
import { contentStyles } from "@/components/content/content.styles"
import { SectionHeader } from "@/components/content/section-header"
import type { ContentRailProps } from "@/components/content/content-rail.types"

export function ContentRail({
    title,
    eyebrow,
    description,
    actionLabel,
    onPressAction,
    products,
}: ContentRailProps) {
    if (!products.length) {
        return null
    }

    return (
        <View style={contentStyles.railSection} testID="product-rail">
            <SectionHeader
                title={title}
                eyebrow={eyebrow}
                description={description}
                actionLabel={actionLabel}
                onPressAction={onPressAction}
            />

            <ImageCarousel products={products} />
        </View>
    )
}
