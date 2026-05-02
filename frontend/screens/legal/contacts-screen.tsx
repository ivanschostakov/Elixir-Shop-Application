import { View } from "react-native"

import { FeedTemplate } from "@/components/templates/feed-template"
import { LegalContent } from "@/components/legal/legal-content"
import { legalContentStyles } from "@/components/legal/legal-content.styles"
import { LEGAL_CONTACTS_MARKDOWN } from "@/constants/legal-content"

export default function ContactsScreen() {
    return (
        <FeedTemplate
            contentContainerStyle={legalContentStyles.content}
            scrollViewStyle={legalContentStyles.screen}
            style={legalContentStyles.screen}
        >
            <View style={legalContentStyles.documentWrap}>
                <LegalContent hideFirstHeading markdown={LEGAL_CONTACTS_MARKDOWN} />
            </View>
        </FeedTemplate>
    )
}
