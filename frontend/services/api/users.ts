import { ENDPOINTS } from "@/services/api/constants"
import { apiDelete, apiGet, apiPostMultipart } from "@/services/api/client"
import type { AvatarResponse, UploadableAvatarImage } from "@/services/api/users.types"

function usersPath(path: string) {
    return `${ENDPOINTS.USERS}${path}`
}

export function getMyAvatar() {
    return apiGet<AvatarResponse>(usersPath("/me/avatar"))
}

export function deleteMyAvatar() {
    return apiDelete(usersPath("/me/avatar"))
}

export function uploadMyAvatar(image: UploadableAvatarImage) {
    const formData = new FormData()

    formData.append("image", {
        uri: image.uri,
        name: image.fileName ?? "avatar.jpg",
        type: image.mimeType ?? "image/jpeg",
    } as unknown as Blob)

    return apiPostMultipart<AvatarResponse>(usersPath("/me/avatar"), formData)
}
