import { ActivityIndicator, Pressable, Text, View } from "react-native"

import { legalContentStyles } from "@/components/legal/legal-content.styles"
import { LegalContent } from "@/components/legal/legal-content"
import { FeedTemplate } from "@/components/templates/feed-template"
import { buildRequisitesMarkdown } from "@/constants/legal-content"
import { useRequisites } from "@/hooks/legal/use-requisites"
import { useLanguage } from "@/providers/language-provider"
import { colors } from "@/theme/colors"

export default function RequisitesScreen() {
    const { t } = useLanguage()
    const { requisites, error, loading, reload } = useRequisites()
    const markdown = buildRequisitesMarkdown(requisites)

    return (
        <FeedTemplate
            contentContainerStyle={legalContentStyles.content}
            scrollViewStyle={legalContentStyles.screen}
            style={legalContentStyles.screen}
        >
            <View style={legalContentStyles.documentWrap}>
                <LegalContent hideFirstHeading markdown={markdown} />
            </View>

            {loading ? (
                <View style={legalContentStyles.statusRow}>
                    <ActivityIndicator color={colors.primary} />
                </View>
            ) : null}

            {error ? (
                <View style={legalContentStyles.statusRow}>
                    <Text style={legalContentStyles.body}>{error}</Text>
                    <Pressable onPress={() => void reload()}>
                        <Text style={legalContentStyles.linkButton}>{t("common.retry")}</Text>
                    </Pressable>
                </View>
            ) : null}
        </FeedTemplate>
    )
}
