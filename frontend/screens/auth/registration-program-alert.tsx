import { useCallback, useEffect, useRef, useState } from "react"
import { ActivityIndicator, Alert, Modal, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native"

import { useLanguage } from "@/providers/language-provider"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { createAuthSharedStyles } from "@/screens/auth/auth-shared.styles"
import { chooseRegistrationProgram } from "@/services/auth/auth"
import type { AuthUser } from "@/services/auth/auth.types"
import { cacheAuthUser } from "@/services/auth/session"

export default function RegistrationProgramAlert({ onComplete }: { onComplete: (user: AuthUser) => void }) {
    const { t } = useLanguage()
    const styles = useThemeStyles(createAuthSharedStyles)
    const [phase, setPhase] = useState<"choice" | "code" | "saving">("choice")
    const [code, setCode] = useState("")
    const [error, setError] = useState("")
    const alive = useRef(true)
    useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])

    const save = useCallback(async (program: "bonus" | "partner", promo?: string) => {
        if (!alive.current) return
        setError("")
        setPhase("saving")
        try {
            const user = await chooseRegistrationProgram(program, promo)
            if (alive.current) {
                cacheAuthUser(user)
                onComplete(user)
            }
        } catch (cause) {
            if (!alive.current) return
            setError(cause instanceof Error ? cause.message : t("profile.referral.programSelectionFailed"))
            setPhase(promo ? "code" : "choice")
        }
    }, [onComplete, t])

    useEffect(() => {
        if (phase !== "choice" || Platform.OS === "web") return
        Alert.alert(t("auth.register.programTitle"), error || t("auth.register.programChoiceHint"), [
            { text: t("auth.register.haveInvitationCode"), onPress: () => { if (alive.current) setPhase("code") } },
            { text: t("auth.register.useCompanyCode"), onPress: () => void save("partner") },
            { text: t("auth.register.bonusProgram"), onPress: () => void save("bonus") },
        ], { cancelable: false })
    }, [error, phase, save, t])

    if (phase === "choice" && Platform.OS !== "web") return null
    return (
        <Modal transparent animationType="fade" visible onRequestClose={() => { if (phase === "code") setPhase("choice") }}>
            <View style={layout.overlay}>
                <View style={[styles.card, styles.container, layout.card]}>
                    <Text style={styles.fieldLabel}>{t("auth.register.programTitle")}</Text>
                    {error ? <Text accessibilityRole="alert" style={styles.helperText}>{error}</Text> : null}
                    {phase === "saving" ? <ActivityIndicator /> : phase === "code" ? <>
                        <Text style={styles.helperText}>{t("auth.register.promoTitle")}</Text>
                        <TextInput autoFocus autoCapitalize="none" autoCorrect={false} value={code}
                            onChangeText={setCode} style={styles.input} placeholder={t("auth.register.promoPlaceholder")} />
                        <Pressable disabled={!code.trim()} style={styles.primaryButton} onPress={() => void save("partner", code.trim())}>
                            <Text style={styles.primaryButtonText}>{t("profile.referral.chooseProgramAction")}</Text>
                        </Pressable>
                        <Pressable style={styles.secondaryButton} onPress={() => setPhase("choice")}>
                            <Text style={styles.secondaryButtonText}>{t("auth.register.backToProgramChoice")}</Text>
                        </Pressable>
                    </> : <>
                        <Text style={styles.helperText}>{t("auth.register.programChoiceHint")}</Text>
                        <Pressable style={styles.secondaryButton} onPress={() => setPhase("code")}>
                            <Text style={styles.secondaryButtonText}>{t("auth.register.haveInvitationCode")}</Text>
                        </Pressable>
                        <Pressable style={styles.secondaryButton} onPress={() => void save("partner")}>
                            <Text style={styles.secondaryButtonText}>{t("auth.register.useCompanyCode")}</Text>
                        </Pressable>
                        <Pressable style={styles.secondaryButton} onPress={() => void save("bonus")}>
                            <Text style={styles.secondaryButtonText}>{t("auth.register.bonusProgram")}</Text>
                        </Pressable>
                    </>}
                </View>
            </View>
        </Modal>
    )
}

const layout = StyleSheet.create({
    overlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.5)", alignItems: "center", justifyContent: "center", padding: 24 },
    card: { flex: 0, borderRadius: 16, padding: 20 },
})
