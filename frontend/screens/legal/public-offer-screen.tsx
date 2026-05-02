import { View } from "react-native"

import { LegalContent } from "@/components/legal/legal-content"
import { legalContentStyles } from "@/components/legal/legal-content.styles"
import { FeedTemplate } from "@/components/templates/feed-template"
import { LEGAL_OFFER_MARKDOWN } from "@/constants/legal-content"

export default function PublicOfferScreen() {
    return (
        <FeedTemplate
            contentContainerStyle={legalContentStyles.content}
            scrollViewStyle={legalContentStyles.screen}
            style={legalContentStyles.screen}
        >
            <View style={legalContentStyles.documentWrap}>
                <LegalContent hideFirstHeading markdown={LEGAL_OFFER_MARKDOWN} />
            </View>
        </FeedTemplate>
    )
}
