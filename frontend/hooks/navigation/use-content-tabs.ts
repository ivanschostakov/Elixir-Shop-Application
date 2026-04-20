import { useGlobalSearchParams, useRouter } from "expo-router"

import type { ContentTabBarItem } from "@/components/content/content-tab-bar"
import { ROUTES } from "@/constants/routes"

export type ContentTab = "articles" | "products"

type ContentTabLabels = {
    articles: string
    products: string
}

export function resolveContentTab(tabParam?: string | string[]): ContentTab {
    const resolvedTab = Array.isArray(tabParam) ? tabParam[0] : tabParam
    return resolvedTab === "articles" ? "articles" : "products"
}

export function isContentTabsRoute(pathname: string) {
    return pathname === ROUTES.discover || pathname === ROUTES.favorites
}

export function useContentTabs(pathname: string, labels: ContentTabLabels) {
    const router = useRouter()
    const params = useGlobalSearchParams<{ tab?: string | string[] }>()
    const activeTab = resolveContentTab(params.tab)
    const showContentTabs = isContentTabsRoute(pathname)
    const tabsPath = pathname === ROUTES.favorites ? ROUTES.favorites : ROUTES.discover

    const tabs: ContentTabBarItem[] = showContentTabs
        ? [
              {
                  key: "products",
                  label: labels.products,
                  isActive: activeTab === "products",
                  onPress: () => {
                      if (activeTab !== "products") {
                          router.replace({
                              pathname: tabsPath,
                              params: { tab: "products" },
                          })
                      }
                  },
              },
              {
                  key: "articles",
                  label: labels.articles,
                  isActive: activeTab === "articles",
                  onPress: () => {
                      if (activeTab !== "articles") {
                          router.replace({
                              pathname: tabsPath,
                              params: { tab: "articles" },
                          })
                      }
                  },
              },
          ]
        : []

    return {
        activeTab,
        isProductsTab: activeTab === "products",
        showContentTabs,
        tabs,
    }
}
