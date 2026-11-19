import { useCallback, useEffect, useState, type ReactNode } from "react"
import * as Application from "expo-application"
import { ActivityIndicator, AppState, Linking, Platform, Pressable, Text, View, type AppStateStatus } from "react-native"

import { getAppVersionPolicy } from "@/services/api/app-version"
import type { AppVersionPolicy } from "@/services/api/app-version.types"
import { useTheme } from "@/providers/theme-provider"
import { darkColors, lightColors } from "@/theme/colors"
import { versionGateStyles } from "@/components/navigation/version-gate.styles"

type VersionBlock = {
    storeUrl: string
}

type VersionGateProps = {
    children: ReactNode
}

function numericVersion(value: string | null | undefined): number {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
}

function resolveVersionBlock(policy: AppVersionPolicy): VersionBlock | null {
    if (Platform.OS === "ios") {
        const nativeBuild = numericVersion(Application.nativeBuildVersion)
        if (nativeBuild < policy.ios.minimumBuild) {
            return { storeUrl: policy.ios.storeUrl }
        }
        return null
    }

    if (Platform.OS === "android") {
        const versionCode = numericVersion(Application.nativeBuildVersion)
        if (versionCode < policy.android.minimumVersionCode) {
            return { storeUrl: policy.android.storeUrl }
        }
    }

    return null
}

async function openStoreUrl(storeUrl: string): Promise<boolean> {
    if (!storeUrl) {
        return false
    }

    const canOpen = await Linking.canOpenURL(storeUrl).catch(() => false)
    if (!canOpen) {
        return false
    }

    await Linking.openURL(storeUrl)
    return true
}

export function VersionGate({ children }: VersionGateProps) {
    const { isDark } = useTheme()
    const palette = isDark ? darkColors : lightColors
    const [isChecking, setIsChecking] = useState(true)
    const [block, setBlock] = useState<VersionBlock | null>(null)
    const [isUpdating, setIsUpdating] = useState(false)
    const [updateError, setUpdateError] = useState<string | null>(null)

    const checkVersionPolicy = useCallback(async () => {
        if (Platform.OS === "web") {
            setBlock(null)
            setIsChecking(false)
            return
        }

        try {
            const policy = await getAppVersionPolicy()
            setBlock(resolveVersionBlock(policy))
            setUpdateError(null)
        } catch {
            setBlock(null)
        } finally {
            setIsChecking(false)
        }
    }, [])

    useEffect(() => {
        void checkVersionPolicy()
    }, [checkVersionPolicy])

    useEffect(() => {
        if (Platform.OS === "web") {
            return
        }

        let previousAppState: AppStateStatus = AppState.currentState
        const subscription = AppState.addEventListener("change", (nextAppState) => {
            if (previousAppState !== "active" && nextAppState === "active") {
                void checkVersionPolicy()
            }
            previousAppState = nextAppState
        })

        return () => {
            subscription.remove()
        }
    }, [checkVersionPolicy])

    const handleUpdate = async () => {
        if (!block || isUpdating) {
            return
        }

        setIsUpdating(true)
        setUpdateError(null)

        try {
            const didOpenStore = await openStoreUrl(block.storeUrl)
            if (!didOpenStore) {
                setUpdateError("Update link is not configured yet. Please contact support.")
            }
        } catch {
            const didOpenStore = await openStoreUrl(block.storeUrl)
            if (!didOpenStore) {
                setUpdateError("Could not start the update. Please try again later.")
            }
        } finally {
            setIsUpdating(false)
        }
    }

    if (Platform.OS === "web") {
        return <>{children}</>
    }

    if (isChecking) {
        return (
            <View style={[versionGateStyles.loadingScreen, { backgroundColor: palette.pageBackground }]}>
                <ActivityIndicator color={palette.primary} />
            </View>
        )
    }

    if (!block) {
        return <>{children}</>
    }

    const bodyText = "A newer App Store or Google Play version is required to continue."

    return (
        <View style={[versionGateStyles.screen, { backgroundColor: palette.pageBackground }]}>
            <View style={[versionGateStyles.card, { backgroundColor: palette.surface, borderColor: palette.border }]}>
                <Text style={[versionGateStyles.eyebrow, { color: palette.mutedText }]}>Elixir Peptide</Text>
                <Text style={[versionGateStyles.title, { color: palette.text }]}>Update required</Text>
                <Text style={[versionGateStyles.text, { color: palette.stateText }]}>{bodyText}</Text>

                <Pressable
                    accessibilityRole="button"
                    disabled={isUpdating}
                    onPress={() => {
                        void handleUpdate()
                    }}
                    style={({ pressed }) => [
                        versionGateStyles.button,
                        { backgroundColor: palette.primary },
                        pressed && versionGateStyles.buttonPressed,
                        isUpdating && versionGateStyles.buttonDisabled,
                    ]}
                >
                    <Text style={versionGateStyles.buttonText}>
                        {isUpdating ? "Updating..." : "Update app"}
                    </Text>
                </Pressable>

                {updateError ? (
                    <Text style={[versionGateStyles.helperText, { color: palette.danger }]}>{updateError}</Text>
                ) : null}
            </View>
        </View>
    )
}
