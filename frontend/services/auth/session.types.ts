export type AuthTokens = {
    accessToken: string
    refreshToken: string
    sessionId: number
}

export type SessionListener = (tokens: AuthTokens | null) => void
export type RefreshHandler = () => Promise<AuthTokens | null>
