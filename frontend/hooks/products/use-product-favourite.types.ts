export type UseProductFavouriteResult = {
    isFavourite: boolean
    loading: boolean
    updating: boolean
    error: string | null
    toggleFavourite: () => Promise<boolean>
}
