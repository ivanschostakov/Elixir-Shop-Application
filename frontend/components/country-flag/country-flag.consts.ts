import AeFlag from "@/assets/icons/countries/flag-for-flag-united-arab-emirates-svgrepo-com.svg"
import AmFlag from "@/assets/icons/countries/flag-for-flag-armenia-svgrepo-com.svg"
import AzFlag from "@/assets/icons/countries/flag-for-flag-azerbaijan-svgrepo-com.svg"
import BdFlag from "@/assets/icons/countries/flag-for-flag-bangladesh-svgrepo-com.svg"
import ByFlag from "@/assets/icons/countries/flag-for-flag-belarus-svgrepo-com.svg"
import CnFlag from "@/assets/icons/countries/flag-for-flag-china-svgrepo-com.svg"
import GeFlag from "@/assets/icons/countries/flag-for-flag-georgia-svgrepo-com.svg"
import IdFlag from "@/assets/icons/countries/flag-for-flag-indonesia-svgrepo-com.svg"
import IlFlag from "@/assets/icons/countries/flag-for-flag-israel-svgrepo-com.svg"
import InFlag from "@/assets/icons/countries/flag-for-flag-india-svgrepo-com.svg"
import JpFlag from "@/assets/icons/countries/flag-for-flag-japan-svgrepo-com.svg"
import KgFlag from "@/assets/icons/countries/flag-for-flag-kyrgyzstan-svgrepo-com.svg"
import KzFlag from "@/assets/icons/countries/flag-for-flag-kazakhstan-svgrepo-com.svg"
import MdFlag from "@/assets/icons/countries/flag-for-flag-moldova-svgrepo-com.svg"
import MnFlag from "@/assets/icons/countries/flag-for-flag-mongolia-svgrepo-com.svg"
import RsFlag from "@/assets/icons/countries/flag-for-flag-serbia-svgrepo-com.svg"
import RuFlag from "@/assets/icons/countries/flag-for-flag-russia-svgrepo-com.svg"
import ThFlag from "@/assets/icons/countries/flag-for-flag-thailand-svgrepo-com.svg"
import UsFlag from "@/assets/icons/countries/flag-for-flag-united-states-svgrepo-com.svg"
import UzFlag from "@/assets/icons/countries/flag-for-flag-uzbekistan-svgrepo-com.svg"
import VnFlag from "@/assets/icons/countries/flag-for-flag-vietnam-svgrepo-com.svg"

export const COUNTRY_FLAGS = {
    AE: AeFlag,
    AM: AmFlag,
    AZ: AzFlag,
    BD: BdFlag,
    BY: ByFlag,
    CN: CnFlag,
    GE: GeFlag,
    ID: IdFlag,
    IL: IlFlag,
    IN: InFlag,
    JP: JpFlag,
    KG: KgFlag,
    KZ: KzFlag,
    MD: MdFlag,
    MN: MnFlag,
    RS: RsFlag,
    RU: RuFlag,
    TH: ThFlag,
    US: UsFlag,
    UZ: UzFlag,
    VN: VnFlag,
} as const

export const COUNTRY_SELECTOR_CODES = [
    "RU",
    "BY",
    "KZ",
    "AZ",
    "MD",
    "AM",
    "UZ",
    "KG",
    "GE",
    "MN",
    "CN",
    "JP",
    "RS",
    "IL",
    "AE",
    "IN",
    "BD",
    "VN",
    "TH",
    "ID",
    "US",
] as const

// The current svgrepo flag assets all use a square 36x36 viewBox.
export const COUNTRY_FLAG_ASPECT_RATIO = 1
