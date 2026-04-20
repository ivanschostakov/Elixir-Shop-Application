export type AvatarResponse = {
    image_url: string | null
}

export type UploadableAvatarImage = {
    uri: string
    fileName?: string | null
    mimeType?: string | null
}
