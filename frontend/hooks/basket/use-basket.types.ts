import type { BasketRead } from "@/types/basket"

type BasketReload = (options?: { showLoading?: boolean }) => Promise<BasketRead | null>

export type UseBasketResult = {
    basket: BasketRead | null
    loading: boolean
    error: string | null
    reload: BasketReload
}

export type UseBasketMutationsResult = {
    updating: boolean
    error: string | null
    addItem: (variantId: number, quantity?: number) => Promise<BasketRead>
    updateItemQuantity: (itemId: number, quantity: number) => Promise<BasketRead>
    removeItem: (itemId: number) => Promise<BasketRead>
    clear: () => Promise<BasketRead>
}
