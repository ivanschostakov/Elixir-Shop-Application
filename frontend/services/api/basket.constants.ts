import { ENDPOINTS } from "@/services/api/constants"

export const basketEndpoint = `${ENDPOINTS.USERS}/me/basket`
export const basketItemsEndpoint = `${basketEndpoint}/items`
