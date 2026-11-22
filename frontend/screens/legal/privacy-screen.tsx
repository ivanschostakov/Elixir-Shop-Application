import { View } from "react-native"
import { LegalContent } from "@/components/legal/legal-content"
import { createLegalContentStyles } from "@/components/legal/legal-content.styles"
import { FeedTemplate } from "@/components/templates/feed-template"
import { PRIVACY_POLICY } from "@/constants/privacy-policy"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"

export default function PrivacyScreen() {
    const styles = useThemeStyles(createLegalContentStyles)
    const { language } = useLanguage()
    return <FeedTemplate contentContainerStyle={styles.content} scrollViewStyle={styles.screen} style={styles.screen}>
        <View style={styles.documentWrap}><LegalContent markdown={PRIVACY_POLICY[language]} /></View>
    </FeedTemplate>
}
