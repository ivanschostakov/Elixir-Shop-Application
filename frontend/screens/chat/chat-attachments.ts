import type { ImagePickerAsset } from "expo-image-picker"
import type { UploadableSupportAttachment } from "@/services/api/support.types"

export function createAttachmentFromImagePickerAsset(asset: ImagePickerAsset): UploadableSupportAttachment {
    return {
        fileName: asset.fileName ?? asset.uri.split("/").pop()?.split("?")[0] ?? "photo.jpg",
        mimeType: asset.mimeType ?? "image/jpeg",
        uri: asset.uri,
    }
}
