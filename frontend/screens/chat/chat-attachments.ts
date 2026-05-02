import { Platform } from "react-native"
import * as ImagePicker from "expo-image-picker"
import * as MediaLibrary from "expo-media-library"

import { API_BASE_URL } from "@/services/api/constants"
import type { AIAttachmentRead, UploadableChatAttachment } from "@/services/api/ai-chat.types"
import {
    CHAT_IMAGE_ATTACHMENT_EXTENSIONS,
    DIRECT_ATTACHMENT_URI_PATTERN,
    MESSAGE_IMAGE_MAX_ASPECT_RATIO,
    MESSAGE_IMAGE_MIN_ASPECT_RATIO,
} from "@/screens/chat/chat-screen.constants"

export function createAttachmentFromImagePickerAsset(asset: ImagePicker.ImagePickerAsset): UploadableChatAttachment {
    return {
        fileName: asset.fileName ?? getFileNameFromUri(asset.uri, "photo.jpg"),
        mimeType: asset.mimeType ?? guessMimeTypeFromFilename(asset.fileName ?? asset.uri, "image/jpeg"),
        uri: asset.uri,
    }
}

export async function createAttachmentFromMediaAsset(asset: MediaLibrary.Asset): Promise<UploadableChatAttachment> {
    const assetInfo = await MediaLibrary.getAssetInfoAsync(asset)
    const uri = assetInfo.localUri ?? assetInfo.uri ?? asset.uri

    return {
        fileName: assetInfo.filename ?? asset.filename ?? getFileNameFromUri(uri, "photo.jpg"),
        mimeType: guessMimeTypeFromFilename(assetInfo.filename ?? asset.filename, "image/jpeg"),
        uri,
    }
}

export function getAttachmentDisplayName(attachment: UploadableChatAttachment) {
    return attachment.fileName ?? getFileNameFromUri(attachment.uri, "attachment")
}

export function getReadAttachmentDisplayName(attachment: AIAttachmentRead) {
    return attachment.original_filename || attachment.filename || "attachment"
}

export function isUploadablePhotoAttachment(attachment: UploadableChatAttachment) {
    if (attachment.mimeType?.toLowerCase().startsWith("image/")) {
        return true
    }
    return CHAT_IMAGE_ATTACHMENT_EXTENSIONS.has(getAttachmentExtension(attachment.fileName ?? attachment.uri))
}

export function isImageAttachment(attachment: AIAttachmentRead) {
    if (attachment.type === "image" || attachment.mime_type?.toLowerCase().startsWith("image/")) {
        return true
    }
    return CHAT_IMAGE_ATTACHMENT_EXTENSIONS.has(
        getAttachmentExtension(attachment.original_filename || attachment.filename || String(attachment.relative_path)),
    )
}

export function getReadAttachmentUri(attachment: AIAttachmentRead) {
    const rawPath = String(attachment.relative_path || "")

    if (DIRECT_ATTACHMENT_URI_PATTERN.test(rawPath)) {
        return rawPath
    }

    const normalizedPath = rawPath.replace(/^\/+/, "")
    const mediaPath = normalizedPath.startsWith("media/")
        ? normalizedPath
        : `media/attachments/${normalizedPath}`

    return `${getApiMediaBaseUrl()}/${encodePathSegments(mediaPath)}`
}

export function normalizeImageAspectRatio(width: number | undefined, height: number | undefined) {
    if (!width || !height) {
        return 1
    }

    const ratio = width / height
    return Math.min(MESSAGE_IMAGE_MAX_ASPECT_RATIO, Math.max(MESSAGE_IMAGE_MIN_ASPECT_RATIO, ratio))
}

export function formatVoiceDuration(durationMillis: number) {
    const totalSeconds = Math.max(0, Math.floor(durationMillis / 1000))
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes}:${seconds.toString().padStart(2, "0")}`
}

export function getVoiceRecordingFilename(uri: string) {
    const fallbackFilename = Platform.OS === "web" ? "voice.webm" : "voice.m4a"
    const filename = getFileNameFromUri(uri, fallbackFilename)

    if (getAttachmentExtension(filename)) {
        return filename
    }

    return fallbackFilename
}

export function getVoiceRecordingMimeType(uri: string) {
    const extension = getAttachmentExtension(uri)
    const mimeTypesByExtension: Record<string, string> = {
        "3gp": "audio/3gpp",
        aac: "audio/aac",
        caf: "audio/x-caf",
        m4a: "audio/m4a",
        mp3: "audio/mpeg",
        mp4: "audio/mp4",
        wav: "audio/wav",
        webm: "audio/webm",
    }

    return mimeTypesByExtension[extension] ?? (Platform.OS === "web" ? "audio/webm" : "audio/m4a")
}

function getAttachmentExtension(value: string | null | undefined) {
    const cleanValue = (value || "").split("?")[0] ?? ""
    return cleanValue.split(".").pop()?.toLowerCase() || ""
}

function getFileNameFromUri(uri: string, fallbackFilename: string) {
    const cleanUri = uri.split("?")[0] ?? uri
    const filename = cleanUri.split("/").filter(Boolean).pop()
    return filename || fallbackFilename
}

function guessMimeTypeFromFilename(filename: string | null | undefined, fallbackMimeType: string) {
    if (!filename) {
        return fallbackMimeType
    }

    const extension = filename.split(".").pop()?.toLowerCase()
    if (!extension) {
        return fallbackMimeType
    }

    const mimeTypesByExtension: Record<string, string> = {
        gif: "image/gif",
        heic: "image/heic",
        heif: "image/heif",
        jpeg: "image/jpeg",
        jpg: "image/jpeg",
        png: "image/png",
        webp: "image/webp",
    }

    return mimeTypesByExtension[extension] ?? fallbackMimeType
}

function getApiMediaBaseUrl() {
    const normalizedApiBaseUrl = API_BASE_URL.replace(/\/+$/, "")
    return normalizedApiBaseUrl.endsWith("/api")
        ? normalizedApiBaseUrl.slice(0, -4)
        : normalizedApiBaseUrl
}

function encodePathSegments(path: string) {
    return path
        .split("/")
        .filter(Boolean)
        .map((segment) => encodeURIComponent(segment))
        .join("/")
}
