export type AttachmentMode = "photo" | "file"

export const CHAT_BACKGROUND_DARK = require("../../assets/images/chat/chat-background-dark.png")
export const CHAT_BACKGROUND_LIGHT = require("../../assets/images/chat/chat-background-light.png")

export const RECENT_PHOTO_LIMIT = 60
export const ATTACHMENT_ICON_COLOR = "#1597DF"
export const MESSAGE_IMAGE_MAX_WIDTH = 286
export const MESSAGE_IMAGE_MIN_ASPECT_RATIO = 0.64
export const MESSAGE_IMAGE_MAX_ASPECT_RATIO = 1.7
export const CHAT_IMAGE_ATTACHMENT_EXTENSIONS = new Set(["gif", "heic", "heif", "jpeg", "jpg", "png", "webp"])
export const DIRECT_ATTACHMENT_URI_PATTERN = /^(asset|content|data|file|http|https|ph):/i
export const SAFE_LINK_PROTOCOL_PATTERN = /^(https?:\/\/|mailto:)/i
export const INTERNAL_PRODUCT_LINK_PATTERN = /^\/products\/(\d+)(?:[/?#].*)?$/
export const CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD = 140
export const CHAT_RECORDING_AUDIO_MODE = {
    allowsRecording: true,
    interruptionMode: "doNotMix",
    playsInSilentMode: true,
    shouldPlayInBackground: false,
    shouldRouteThroughEarpiece: false,
} as const
export const CHAT_IDLE_AUDIO_MODE = {
    ...CHAT_RECORDING_AUDIO_MODE,
    allowsRecording: false,
} as const
