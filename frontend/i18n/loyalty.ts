import { translate } from "@/i18n/translations"

export function partnerOfferBody(companyCode: string | null) {
    return translate("milestone.offerBody") + (companyCode ? " " + translate("milestone.companyCode").replace("{code}", companyCode) : "")
}
