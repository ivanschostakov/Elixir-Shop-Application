import { ENDPOINTS } from "@/services/api/constants"
import { apiDelete, apiFetch, apiGet, apiPost, apiPostMultipart } from "@/services/api/client"
import type {
    AvatarResponse,
    DepositResponse,
    DeleteMyPushTokenPayload,
    DeleteMyPushTokenResponse,
    MyPushTokenResponse,
    ReferralProfileResponse,
    ReferrerCodeAttachPayload,
    ReferrerCodeCheckPayload,
    ReferrerCodeCheckResponse,
    UploadableAvatarImage,
    UpsertMyPushTokenPayload,
} from "@/services/api/users.types"

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

export function registerMyPushToken(payload: UpsertMyPushTokenPayload) {
    return apiPost<MyPushTokenResponse, UpsertMyPushTokenPayload>(usersPath("/me/push-tokens"), payload)
}

export function deleteMyPushToken(payload: DeleteMyPushTokenPayload) {
    return apiFetch<DeleteMyPushTokenResponse>(
        usersPath("/me/push-tokens"),
        {
            method: "DELETE",
            body: JSON.stringify(payload),
        },
    )
}

export function getMyReferralProfile() {
    return apiGet<ReferralProfileResponse>(usersPath("/me/referral-profile"))
}

export function checkMyReferrerCode(payload: ReferrerCodeCheckPayload) {
    return apiPost<ReferrerCodeCheckResponse, ReferrerCodeCheckPayload>(
        usersPath("/me/referral-profile/referrer-code/check"),
        payload,
    )
}

export function attachMyReferrerCode(payload: ReferrerCodeAttachPayload) {
    return apiPost<ReferralProfileResponse, ReferrerCodeAttachPayload>(
        usersPath("/me/referral-profile/referrer-code"),
        payload,
    )
}

export function getMyDeposit() {
    return apiGet<DepositResponse>(usersPath("/me/deposit"))
}
