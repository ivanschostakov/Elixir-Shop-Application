import { useCallback, useState } from "react"
import { Alert, Pressable, Text, View } from "react-native"
import { useFocusEffect } from "expo-router"
import { LegalContent } from "@/components/legal/legal-content"
import { createLegalContentStyles } from "@/components/legal/legal-content.styles"
import { FeedTemplate } from "@/components/templates/feed-template"
import { PRIVACY_POLICY } from "@/constants/privacy-policy"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { getAiDataConsent, setAiDataConsent, type AiDataConsent } from "@/services/api/ai-data-consent"

export default function PrivacyScreen() {
    const styles = useThemeStyles(createLegalContentStyles)
    const { language, t } = useLanguage()
    const { palette } = useTheme()
    const { user } = useAuth()
    const userId = user?.id
    const [consent, setConsent] = useState<AiDataConsent | null>(null)
    const [busy, setBusy] = useState(false)
    const [failed, setFailed] = useState(false)
    const load = useCallback(async () => { setFailed(false); try { setConsent(await getAiDataConsent()) } catch { setFailed(true) } }, [])
    useFocusEffect(useCallback(() => {
        let active = true
        setConsent(null); setFailed(false)
        if (userId) void getAiDataConsent().then(value => { if (active) setConsent(value) }).catch(() => { if (active) setFailed(true) })
        return () => { active = false }
    }, [userId]))
    const revoke = async () => {
        if (!consent || busy) return
        setBusy(true)
        try { setConsent(await setAiDataConsent(false, consent.version)); Alert.alert(t("privacy.revoked")) }
        catch { Alert.alert(t("privacy.failed")) }
        finally { setBusy(false) }
    }
    return <FeedTemplate contentContainerStyle={styles.content} scrollViewStyle={styles.screen} style={styles.screen}>
        <View style={styles.documentWrap}>
            <LegalContent markdown={PRIVACY_POLICY[language]} />
            {user && failed ? <Pressable accessibilityRole="button" onPress={() => void load()}><Text style={{ color: palette.primary, paddingVertical: 16 }}>{t("privacy.retry")}</Text></Pressable> : null}
            {consent?.granted ? <Pressable accessibilityRole="button" disabled={busy} onPress={() => void revoke()}><Text style={{ color: palette.danger, paddingVertical: 16 }}>{t("privacy.revoke")}</Text></Pressable> : consent ? <Text style={{ color: palette.text, paddingVertical: 16 }}>{t("privacy.disabled")}</Text> : null}
        </View>
    </FeedTemplate>
}
