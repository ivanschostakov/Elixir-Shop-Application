import { useCallback, useEffect, useState, type ReactNode } from "react"
import { ActivityIndicator, Platform, Pressable, Text, View } from "react-native"

import { useAuth } from "@/providers/auth-provider"
import { startTelegramSession } from "@/services/auth/auth"
import type { AuthTokensWithUserResponse, TelegramAuthResponse } from "@/services/auth/auth.types"
import {
    getTelegramInitData,
    initializeTelegramWebApp,
    isTelegramWebAppEnvironment,
    requestTelegramContact,
} from "@/services/telegram/telegram-web-app"
import { telegramWebAppGateStyles } from "@/components/telegram/telegram-web-app-gate.styles"

type TelegramGateStatus =
    | "checking"
    | "contactRequired"
    | "contactRequested"
    | "failed"
    | "notTelegram"

type TelegramWebAppGateProps = {
    children: ReactNode
}

const CONTACT_POLL_ATTEMPTS = 24
const CONTACT_POLL_INTERVAL_MS = 1500

function delay(ms: number) {
    return new Promise((resolve) => {
        setTimeout(resolve, ms)
    })
}

function isTokenResponse(response: TelegramAuthResponse): response is AuthTokensWithUserResponse {
    return "access_token" in response && "refresh_token" in response
}

function GatePanel({
    buttonLabel,
    children,
    error,
    isBusy = false,
    onPress,
    title,
}: {
    buttonLabel?: string
    children: ReactNode
    error?: string | null
    isBusy?: boolean
    onPress?: () => void
    title: string
}) {
    return (
        <View style={telegramWebAppGateStyles.screen}>
            <View style={telegramWebAppGateStyles.panel}>
                <Text style={telegramWebAppGateStyles.eyebrow}>Elixir Peptide</Text>
                <Text style={telegramWebAppGateStyles.title}>{title}</Text>
                <Text style={telegramWebAppGateStyles.text}>{children}</Text>
                {error ? <Text style={telegramWebAppGateStyles.errorText}>{error}</Text> : null}
                {buttonLabel && onPress ? (
                    <Pressable
                        accessibilityRole="button"
                        disabled={isBusy}
                        onPress={onPress}
                        style={({ pressed }) => [
                            telegramWebAppGateStyles.button,
                            pressed && telegramWebAppGateStyles.buttonPressed,
                            isBusy && telegramWebAppGateStyles.buttonDisabled,
                        ]}
                    >
                        <Text style={telegramWebAppGateStyles.buttonText}>{buttonLabel}</Text>
                    </Pressable>
                ) : null}
            </View>
        </View>
    )
}

function LoadingPanel({ label }: { label: string }) {
    return (
        <View style={telegramWebAppGateStyles.screen}>
            <View style={telegramWebAppGateStyles.panel}>
                <View style={telegramWebAppGateStyles.loadingRow}>
                    <ActivityIndicator color="#2d6aa3" />
                    <Text style={telegramWebAppGateStyles.loadingText}>{label}</Text>
                </View>
            </View>
        </View>
    )
}

export function TelegramWebAppGate({ children }: TelegramWebAppGateProps) {
    const { acceptSession, isAuthenticated, isReady } = useAuth()
    const [status, setStatus] = useState<TelegramGateStatus>("checking")
    const [error, setError] = useState<string | null>(null)
    const [isRequestingContact, setIsRequestingContact] = useState(false)

    const authenticateWithTelegram = useCallback(async (isPolling = false) => {
        const initData = getTelegramInitData()
        if (!initData) {
            setStatus("notTelegram")
            return false
        }

        if (!isPolling) {
            setStatus("checking")
        }

        try {
            const response = await startTelegramSession(initData)
            if (isTokenResponse(response)) {
                acceptSession(response)
                setStatus("checking")
                setError(null)
                return true
            }

            setStatus(isPolling ? "contactRequested" : "contactRequired")
            return false
        } catch {
            setStatus("failed")
            setError("Telegram sign-in is temporarily unavailable.")
            return false
        }
    }, [acceptSession])

    useEffect(() => {
        if (Platform.OS !== "web") {
            return
        }

        initializeTelegramWebApp()
    }, [])

    useEffect(() => {
        if (Platform.OS !== "web") {
            return
        }

        if (!isTelegramWebAppEnvironment()) {
            setStatus("notTelegram")
            return
        }

        if (!isReady || isAuthenticated) {
            return
        }

        void authenticateWithTelegram()
    }, [authenticateWithTelegram, isAuthenticated, isReady])

    const handleShareContact = async () => {
        if (isRequestingContact) {
            return
        }

        setIsRequestingContact(true)
        setError(null)
        setStatus("contactRequested")

        const isShared = await requestTelegramContact()
        if (!isShared) {
            setIsRequestingContact(false)
            setStatus("contactRequired")
            setError("Phone number sharing was cancelled.")
            return
        }

        for (let attempt = 0; attempt < CONTACT_POLL_ATTEMPTS; attempt += 1) {
            await delay(CONTACT_POLL_INTERVAL_MS)
            const isAuthenticatedAfterPoll = await authenticateWithTelegram(true)
            if (isAuthenticatedAfterPoll) {
                setIsRequestingContact(false)
                return
            }
        }

        setIsRequestingContact(false)
        setStatus("contactRequired")
        setError("We have not received the Telegram contact yet. Please try again.")
    }

    if (Platform.OS !== "web") {
        return <>{children}</>
    }

    const isTelegramEnvironment = isTelegramWebAppEnvironment()

    if (isAuthenticated && isTelegramEnvironment) {
        return <>{children}</>
    }

    if (!isReady || status === "checking") {
        return <LoadingPanel label="Opening Telegram shop..." />
    }

    if (!isTelegramEnvironment || status === "notTelegram") {
        return (
            <GatePanel title="Open in Telegram">
                This web version runs inside the Elixir Peptide Telegram app.
            </GatePanel>
        )
    }

    if (status === "contactRequired" || status === "contactRequested") {
        return (
            <GatePanel
                buttonLabel={isRequestingContact ? "Waiting for Telegram..." : "Share Telegram phone"}
                error={error}
                isBusy={isRequestingContact}
                onPress={() => {
                    void handleShareContact()
                }}
                title="Confirm your phone"
            >
                Telegram will ask permission to share the phone number attached to your account.
            </GatePanel>
        )
    }

    return (
        <GatePanel
            buttonLabel="Try again"
            error={error}
            onPress={() => {
                void authenticateWithTelegram()
            }}
            title="Telegram sign-in failed"
        >
            Please try opening the shop again from Telegram.
        </GatePanel>
    )
}
