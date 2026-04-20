import { apiDelete, apiGet, apiPost } from "@/services/api/client"
import { favouriteProductsEndpoint } from "@/services/api/favourites.constants"
import type { FavouriteProductStatus } from "@/services/api/favourites.types"
import type { ProductRead } from "@/types/product"

export function getFavouriteProducts(): Promise<ProductRead[]> {
    return apiGet<ProductRead[]>(favouriteProductsEndpoint)
}

export function getFavouriteProductStatus(productId: number): Promise<FavouriteProductStatus> {
    return apiGet<FavouriteProductStatus>(`${favouriteProductsEndpoint}/${productId}`)
}

export function addFavouriteProduct(productId: number): Promise<FavouriteProductStatus> {
    return apiPost<FavouriteProductStatus, Record<string, never>>(
        `${favouriteProductsEndpoint}/${productId}`,
        {},
    )
}

export function removeFavouriteProduct(productId: number): Promise<void> {
    return apiDelete(`${favouriteProductsEndpoint}/${productId}`)
}
