export type ChatMode = "ai" | "community" | "support"

export function isCommunityChatAvailable(platform: string, privateIosFeatures = false): boolean {
    return platform !== "ios" || privateIosFeatures
}

export function isMentorAvailable(platform: string, privateIosFeatures = false): boolean {
    return platform !== "web" && isCommunityChatAvailable(platform, privateIosFeatures)
}

export function resolveChatMode(value: unknown, platform: string, privateIosFeatures = false): ChatMode | null {
    if (value !== "ai" && value !== "community" && value !== "support") return null
    return value === "community" && !isCommunityChatAvailable(platform, privateIosFeatures) ? "ai" : value
}
