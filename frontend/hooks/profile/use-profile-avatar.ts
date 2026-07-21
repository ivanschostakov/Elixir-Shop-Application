import { useCallback, useEffect, useState } from "react"
import { Alert } from "react-native"
import * as ImagePicker from "expo-image-picker"

import type { UseProfileAvatarParams } from "@/hooks/profile/use-profile-avatar.types"
import { resolveApiMediaUri } from "@/services/api/media"
import { deleteMyAvatar, getMyAvatar, uploadMyAvatar } from "@/services/api/users"

const SUPPORTED_AVATAR_MIME_TYPES = new Set(["image/jpeg", "image/png", "image/webp"])

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
                    setAvatarUri(resolveApiMediaUri(avatar.image_url))
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

    const handleChangePhoto = useCallback(async () => {
        if (!userId || isUpdatingAvatar) {
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

            setAvatarUri(resolveApiMediaUri(uploadedImage.image_url))
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
    }, [isUpdatingAvatar, t, userId])

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
