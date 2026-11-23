export type ChatMode = "ai" | "community" | "support"

export function isCommunityChatAvailable(platform: string): boolean {
    return platform === "ios" || platform === "android" || platform === "web"
}

export function isMentorAvailable(platform: string): boolean {
    return platform === "ios" || platform === "android"
}

export function resolveChatMode(value: unknown, platform: string): ChatMode | null {
    if (value !== "ai" && value !== "community" && value !== "support") return null
    return value === "community" && !isCommunityChatAvailable(platform) ? "ai" : value
}
