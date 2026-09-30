import { useEffect, useRef, useState, type ReactNode } from "react"
import { Alert, Keyboard, Modal, Platform, Pressable, ScrollView, Text, View } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { LegalContent } from "@/components/legal/legal-content"
import { PRIVACY_POLICY } from "@/constants/privacy-policy"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { registerAiConsentPrompt } from "@/services/api/ai-data-consent"

export function AiConsentProvider({ children }: { children: ReactNode }) {
    const { user } = useAuth()
    const { t, language } = useLanguage()
    const { palette } = useTheme()
    const insets = useSafeAreaInsets()
    const [visible, setVisible] = useState(false)
    const [policy, setPolicy] = useState(false)
    const resolveRef = useRef<((accepted: boolean) => void) | null>(null)
    const finish = (accepted: boolean) => {
        resolveRef.current?.(accepted)
        resolveRef.current = null
        setVisible(false)
        setPolicy(false)
    }
    useEffect(() => {
        const unregister = registerAiConsentPrompt(() => new Promise<boolean>(resolve => {
            Keyboard.dismiss()
            resolveRef.current?.(false)
            resolveRef.current = resolve
            if (Platform.OS !== "web") {
                const respond = (accepted: boolean) => {
                    if (resolveRef.current !== resolve) return
                    resolveRef.current = null
                    resolve(accepted)
                }
                Alert.alert("OpenAI", t("privacy.aiQuestion"), [
                    { text: t("privacy.notNow"), style: "cancel", onPress: () => respond(false) },
                    { text: t("privacy.agree"), onPress: () => respond(true) },
                ], { cancelable: true, onDismiss: () => respond(false) })
                return
            }
            setPolicy(false)
            setVisible(true)
        }))
        return () => { unregister(); resolveRef.current?.(false); resolveRef.current = null; setVisible(false) }
    }, [t, user?.id])
    if (Platform.OS !== "web") return <>{children}</>
    return <>{children}<Modal visible={visible} transparent animationType="fade" onRequestClose={() => policy ? setPolicy(false) : finish(false)}>
        <View style={{ flex: 1, justifyContent: "center", padding: 24, paddingTop: Math.max(insets.top, 24), paddingBottom: Math.max(insets.bottom, 24), backgroundColor: "rgba(0,0,0,0.55)" }}>
            <View style={{ maxHeight: "90%", padding: 20, borderRadius: 20, backgroundColor: palette.background, gap: 18 }}>
                {policy ? <><ScrollView><LegalContent markdown={PRIVACY_POLICY[language]} /></ScrollView><Pressable accessibilityRole="button" onPress={() => setPolicy(false)}><Text style={{ color: palette.primary, padding: 10 }}>{t("common.close")}</Text></Pressable></> : <>
                    <Text accessibilityRole="header" style={{ color: palette.text, fontSize: 20, fontWeight: "600" }}>OpenAI</Text>
                    <Text style={{ color: palette.text, fontSize: 16 }}>{t("privacy.aiQuestion")}</Text>
                    <Pressable accessibilityRole="link" onPress={() => setPolicy(true)}><Text style={{ color: palette.primary }}>{t("privacy.title")}</Text></Pressable>
                    <View style={{ flexDirection: "row", flexWrap: "wrap", justifyContent: "flex-end", gap: 16 }}>
                        <Pressable accessibilityRole="button" onPress={() => finish(false)}><Text style={{ color: palette.text, padding: 12 }}>{t("privacy.notNow")}</Text></Pressable>
                        <Pressable accessibilityRole="button" onPress={() => finish(true)} style={{ borderRadius: 12, backgroundColor: palette.primary }}><Text style={{ color: "#fff", padding: 12, fontWeight: "600" }}>{t("privacy.agree")}</Text></Pressable>
                    </View>
                </>}
            </View>
        </View>
    </Modal></>
}
