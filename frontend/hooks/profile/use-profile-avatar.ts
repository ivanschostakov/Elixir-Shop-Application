import { useCallback, useEffect, useState } from "react"
import { Alert } from "react-native"
import * as ImagePicker from "expo-image-picker"

import type { UseProfileAvatarParams } from "@/hooks/profile/use-profile-avatar.types"
import { API_BASE_URL } from "@/services/api/constants"
import { deleteMyAvatar, getMyAvatar, uploadMyAvatar } from "@/services/api/users"

const SUPPORTED_AVATAR_MIME_TYPES = new Set(["image/jpeg", "image/png", "image/webp"])

function getApiOrigin() {
    try {
        return new URL(API_BASE_URL).origin
    } catch {
        return ""
    }
}

function resolveAvatarUri(uri: string | null | undefined) {
    if (!uri) {
        return null
    }

    const trimmedUri = uri.trim()
    if (!trimmedUri) {
        return null
    }

    const apiOrigin = getApiOrigin()
    if (!apiOrigin) {
        return trimmedUri
    }

    if (trimmedUri.startsWith("/")) {
        return `${apiOrigin}${trimmedUri}`
    }

    try {
        const avatarUrl = new URL(trimmedUri)
        const apiBaseUrl = new URL(apiOrigin)

        if (avatarUrl.pathname.startsWith("/media/avatars/")) {
            avatarUrl.protocol = apiBaseUrl.protocol
            avatarUrl.host = apiBaseUrl.host
            return avatarUrl.toString()
        }

        return trimmedUri
    } catch {
        return trimmedUri
    }
}

function normalizeAvatarMimeType(mimeType: string | null | undefined) {
    if (!mimeType) {
        return "image/jpeg"
    }

    const normalizedMimeType = mimeType.toLowerCase()
    if (SUPPORTED_AVATAR_MIME_TYPES.has(normalizedMimeType)) {
        return normalizedMimeType
    }

    return "image/jpeg"
}

export function useProfileAvatar({ userId, t }: UseProfileAvatarParams) {
    const [avatarUri, setAvatarUri] = useState<string | null>(null)
    const [isUpdatingAvatar, setIsUpdatingAvatar] = useState(false)
    const [hasMediaPermission, setHasMediaPermission] = useState<boolean | null>(null)

    useEffect(() => {
        if (!userId) {
            setAvatarUri(null)
            return
        }

        let isMounted = true

        const loadAvatarUri = async () => {
            try {
                const avatar = await getMyAvatar()

                if (isMounted) {
                    setAvatarUri(resolveAvatarUri(avatar.image_url))
                }
            } catch {
                if (isMounted) {
                    setAvatarUri(null)
                }
            }
        }

        void loadAvatarUri()

        return () => {
            isMounted = false
        }
    }, [userId])

    useEffect(() => {
        let isMounted = true

        const preloadPermission = async () => {
            try {
                const permission = await ImagePicker.getMediaLibraryPermissionsAsync()

                if (isMounted) {
                    setHasMediaPermission(permission.granted)
                }
            } catch {
                if (isMounted) {
                    setHasMediaPermission(null)
                }
            }
        }

        void preloadPermission()

        return () => {
            isMounted = false
        }
    }, [])

    const ensureMediaPermission = useCallback(async () => {
        if (hasMediaPermission) {
            return true
        }

        let permission = await ImagePicker.getMediaLibraryPermissionsAsync()

        if (!permission.granted) {
            permission = await ImagePicker.requestMediaLibraryPermissionsAsync()
        }

        const granted = permission.granted

        setHasMediaPermission(granted)

        if (!granted) {
            Alert.alert(t("profile.photoPermissionTitle"), t("profile.photoPermissionMessage"))
        }

        return granted
    }, [hasMediaPermission, t])

    const handleChangePhoto = useCallback(async () => {
        if (!userId || isUpdatingAvatar) {
            return
        }

        const hasPermission = await ensureMediaPermission()

        if (!hasPermission) {
            return
        }

        setIsUpdatingAvatar(true)

        try {
            const result = await ImagePicker.launchImageLibraryAsync({
                allowsEditing: true,
                aspect: [1, 1],
                mediaTypes: ["images"],
                quality: 0.8,
            })

            if (result.canceled || !result.assets.length) {
                return
            }

            const asset = result.assets[0]
            const nextAvatarUri = asset?.uri ?? null

            if (!nextAvatarUri) {
                return
            }

            const uploadedImage = await uploadMyAvatar({
                uri: nextAvatarUri,
                fileName: asset?.fileName,
                mimeType: normalizeAvatarMimeType(asset?.mimeType),
            })

            setAvatarUri(resolveAvatarUri(uploadedImage.image_url))
        } catch (uploadError) {
            Alert.alert(
                t("profile.photoErrorTitle"),
                uploadError instanceof Error && uploadError.message
                    ? uploadError.message
                    : t("profile.photoErrorMessage"),
            )
        } finally {
            setIsUpdatingAvatar(false)
        }
    }, [ensureMediaPermission, isUpdatingAvatar, t, userId])

    const handleRemovePhoto = useCallback(async () => {
        if (!userId || isUpdatingAvatar) {
            return
        }

        setIsUpdatingAvatar(true)

        try {
            await deleteMyAvatar()
            setAvatarUri(null)
        } finally {
            setIsUpdatingAvatar(false)
        }
    }, [isUpdatingAvatar, userId])

    return {
        avatarUri,
        isUpdatingAvatar,
        handleChangePhoto,
        handleRemovePhoto,
    }
}
