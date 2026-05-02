import { Pressable, Text, View, Alert, Linking } from "react-native"
import * as Clipboard from "expo-clipboard"

import { legalContentStyles } from "@/components/legal/legal-content.styles"
import { useLanguage } from "@/providers/language-provider"

type LegalContentProps = {
    markdown: string
    hideFirstHeading?: boolean
}

function getLineKind(line: string) {
    if (line.startsWith("### ")) {
        return "h3"
    }
    if (line.startsWith("## ")) {
        return "h2"
    }
    if (line.startsWith("# ")) {
        return "h1"
    }
    return "body"
}

function getLineValue(line: string, kind: ReturnType<typeof getLineKind>) {
    if (kind === "h1") {
        return line.slice(2)
    }
    if (kind === "h2") {
        return line.slice(3)
    }
    if (kind === "h3") {
        return line.slice(4)
    }
    return line
}

export function LegalContent({ markdown, hideFirstHeading = false }: LegalContentProps) {
    const { t } = useLanguage()
    const lines = markdown.replace(/\r/g, "").split("\n")

    const phoneRegex = /(?:\+\d[\d\s\-()]{7,}\d)/
    const emailRegex = /([^\s@]+@[^\s@]+\.[^\s@]+)/

    const handleCopy = async (value: string) => {
        await Clipboard.setStringAsync(value)
        Alert.alert(t("profile.copiedTitle"), value)
    }

    const getFirstPhone = (value: string) => {
        const match = value.match(phoneRegex)
        return match?.[0] ?? null
    }

    const getFirstEmail = (value: string) => {
        const match = value.match(emailRegex)
        return match?.[0] ?? null
    }

    const openPhone = async (rawPhone: string) => {
        const sanitizedPhone = rawPhone.replace(/[^\d+]/g, "")
        const digitCount = sanitizedPhone.replace(/\D/g, "").length
        if (!sanitizedPhone.startsWith("+") || digitCount < 10 || digitCount > 15) {
            await handleCopy(rawPhone)
            return
        }
        const url = `tel:${sanitizedPhone}`
        const canOpen = await Linking.canOpenURL(url).catch(() => false)

        if (!canOpen) {
            await handleCopy(rawPhone)
            return
        }

        await Linking.openURL(url)
    }

    const openEmail = async (email: string) => {
        const url = `mailto:${email}`
        const canOpen = await Linking.canOpenURL(url).catch(() => false)

        if (!canOpen) {
            await handleCopy(email)
            return
        }

        await Linking.openURL(url)
    }

    let hasHiddenFirstHeading = false

    return (
        <View style={legalContentStyles.block}>
            {lines.map((rawLine, index) => {
                const line = rawLine.trim()
                if (!line) {
                    return <View key={`spacer-${index}`} style={legalContentStyles.spacer} />
                }

                const kind = getLineKind(line)
                const value = getLineValue(line, kind)

                if (hideFirstHeading && !hasHiddenFirstHeading && kind === "h1") {
                    hasHiddenFirstHeading = true
                    return null
                }

                if (kind === "h1") {
                    return (
                        <Pressable
                            key={`h1-${index}`}
                            onPress={() => {
                                void handleCopy(value)
                            }}
                        >
                            <Text style={legalContentStyles.h1}>{value}</Text>
                        </Pressable>
                    )
                }

                if (kind === "h2") {
                    return (
                        <Pressable
                            key={`h2-${index}`}
                            onPress={() => {
                                void handleCopy(value)
                            }}
                        >
                            <Text style={legalContentStyles.h2}>{value}</Text>
                        </Pressable>
                    )
                }

                if (kind === "h3") {
                    return (
                        <Pressable
                            key={`h3-${index}`}
                            onPress={() => {
                                void handleCopy(value)
                            }}
                        >
                            <Text style={legalContentStyles.h3}>{value}</Text>
                        </Pressable>
                    )
                }

                const detectedEmail = getFirstEmail(value)
                const detectedPhone = getFirstPhone(value)
                const isEmail = Boolean(detectedEmail)
                const isPhone = Boolean(detectedPhone)
                const shouldOpenLink = isEmail || isPhone

                return (
                    <Pressable
                        key={`body-${index}`}
                        onPress={() => {
                            if (shouldOpenLink) {
                                if (detectedEmail) {
                                    void openEmail(detectedEmail).catch(() => {
                                        void handleCopy(detectedEmail)
                                    })
                                    return
                                }

                                if (detectedPhone) {
                                    void openPhone(detectedPhone).catch(() => {
                                        void handleCopy(detectedPhone)
                                    })
                                    return
                                }

                                return
                            }

                            void handleCopy(value)
                        }}
                    >
                        <Text style={isEmail || isPhone ? legalContentStyles.bodyLink : legalContentStyles.body}>
                            {value}
                        </Text>
                    </Pressable>
                )
            })}
        </View>
    )
}
