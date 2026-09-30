import type { ContentTabBarItem } from "@/components/content/content-tab-bar"
import { ROUTES } from "@/constants/routes"

export function useContentTabs(pathname: string, labels: { products: string }) {
    const showContentTabs = pathname === ROUTES.discover || pathname === ROUTES.favorites
    const tabs: ContentTabBarItem[] = showContentTabs
        ? [{ key: "products", label: labels.products, isActive: true, onPress: () => undefined }]
        : []
    return { tabs, showContentTabs }
}
