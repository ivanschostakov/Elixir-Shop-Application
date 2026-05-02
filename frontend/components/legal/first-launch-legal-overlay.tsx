import { useEffect, useMemo, useRef, useState } from "react"
import * as SecureStore from "expo-secure-store"
import {
    ActivityIndicator,
    Platform,
    Pressable,
    ScrollView,
    StyleSheet,
    Text,
    View,
    type NativeSyntheticEvent,
    type NativeScrollEvent,
} from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { LegalContent } from "@/components/legal/legal-content"
import { legalContentStyles } from "@/components/legal/legal-content.styles"
import { LEGAL_CONTACTS_MARKDOWN, LEGAL_OFFER_MARKDOWN } from "@/constants/legal-content"
import { useLanguage } from "@/providers/language-provider"
import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"

const LEGAL_ACCEPTED_STORAGE_KEY = "elixirshop-legal-accepted-v1"

function getWebStorage() {
    if (typeof window === "undefined" || typeof window.localStorage === "undefined") {
        return null
    }

    return window.localStorage
}

async function readLegalAcceptedFlag(): Promise<boolean> {
    if (Platform.OS === "web") {
        return getWebStorage()?.getItem(LEGAL_ACCEPTED_STORAGE_KEY) === "1"
    }

    try {
        return (await SecureStore.getItemAsync(LEGAL_ACCEPTED_STORAGE_KEY)) === "1"
    } catch {
        return false
    }
}

async function persistLegalAcceptedFlag() {
    if (Platform.OS === "web") {
        getWebStorage()?.setItem(LEGAL_ACCEPTED_STORAGE_KEY, "1")
        return
    }

    try {
        await SecureStore.setItemAsync(LEGAL_ACCEPTED_STORAGE_KEY, "1")
    } catch {
        // Keep in-memory accepted state even if persistence fails.
    }
}

export function FirstLaunchLegalOverlay() {
    const { t } = useLanguage()
    const insets = useSafeAreaInsets()
    const scrollRef = useRef<ScrollView | null>(null)
    const [isHydrating, setIsHydrating] = useState(true)
    const [isAccepted, setIsAccepted] = useState(false)
    const [canAccept, setCanAccept] = useState(false)

    useEffect(() => {
        let isMounted = true

        void readLegalAcceptedFlag().then((accepted) => {
            if (!isMounted) {
                return
            }

            setIsAccepted(accepted)
            setIsHydrating(false)
        })

        return () => {
            isMounted = false
        }
    }, [])

    const markdown = useMemo(
        () => `${LEGAL_CONTACTS_MARKDOWN}\n\n${LEGAL_OFFER_MARKDOWN}`,
        [],
    )

    const handleScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
        if (canAccept) {
            return
        }

        const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent
        const reachedBottom = contentOffset.y + layoutMeasurement.height >= contentSize.height - 20
        if (reachedBottom) {
            setCanAccept(true)
        }
    }

    if (isHydrating || isAccepted) {
        if (isAccepted) {
            return null
        }

        return (
            <View style={styles.loaderBackdrop}>
                <ActivityIndicator color={colors.primary} />
            </View>
        )
    }

    return (
        <View style={styles.overlay}>
            <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
                <Text style={styles.headerTitle}>{t("route.publicOffer")}</Text>
            </View>

            <ScrollView
                ref={(node) => {
                    scrollRef.current = node
                }}
                onScroll={handleScroll}
                scrollEventThrottle={16}
                showsVerticalScrollIndicator
                style={styles.scroll}
                contentContainerStyle={legalContentStyles.content}
            >
                <LegalContent markdown={markdown} />
            </ScrollView>

            <View style={[styles.footer, { paddingBottom: Math.max(insets.bottom, spacing.sm) }]}>
                <Pressable
                    accessibilityRole="button"
                    onPress={() => {
                        if (canAccept) {
                            setIsAccepted(true)
                            void persistLegalAcceptedFlag()
                            return
                        }

                        scrollRef.current?.scrollToEnd({ animated: true })
                    }}
                    style={({ pressed }) => [
                        styles.ctaButton,
                        pressed && styles.ctaButtonPressed,
                    ]}
                >
                    <Text style={styles.ctaButtonText}>
                        {canAccept ? t("legal.agreeCta") : t("legal.scrollCta")}
                    </Text>
                </Pressable>
            </View>
        </View>
    )
}

const styles = StyleSheet.create({
    loaderBackdrop: {
        ...StyleSheet.absoluteFillObject,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: colors.pageBackground,
        zIndex: 999,
    },
    overlay: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: colors.pageBackground,
        zIndex: 999,
    },
    header: {
        borderBottomLeftRadius: 24,
        borderBottomRightRadius: 24,
        paddingHorizontal: spacing.md,
        paddingBottom: spacing.md,
        backgroundColor: colors.pageBackground,
    },
    headerTitle: {
        color: colors.text,
        fontSize: 20,
        fontWeight: "800",
        textAlign: "center",
    },
    scroll: {
        flex: 1,
    },
    footer: {
        borderTopLeftRadius: spacing.xl,
        borderTopRightRadius: spacing.xl,
        paddingTop: spacing.sm,
        paddingHorizontal: spacing.md,
        backgroundColor: colors.pageBackground,
        ...Platform.select({
            web: {
                boxShadow: "0 -4px 16px rgba(0, 0, 0, 0.12)",
            },
            default: {
                shadowColor: "#000000",
                shadowOffset: { width: 0, height: -4 },
                shadowOpacity: 0.12,
                shadowRadius: 16,
            },
        }),
    },
    ctaButton: {
        minHeight: 52,
        borderRadius: 14,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: colors.primary,
        paddingHorizontal: spacing.md,
    },
    ctaButtonPressed: {
        opacity: 0.86,
    },
    ctaButtonText: {
        color: colors.onPrimary,
        fontSize: 16,
        fontWeight: "800",
    },
})
