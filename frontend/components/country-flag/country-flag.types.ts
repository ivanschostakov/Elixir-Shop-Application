import {COUNTRY_FLAGS} from "@/components/country-flag/country-flag.consts";
import {StyleProp, ViewStyle} from "react-native";

export type CountryCode = keyof typeof COUNTRY_FLAGS


type CountryFlagBaseProps = {
    code: CountryCode
    style?: StyleProp<ViewStyle>
}

export type CountryFlagProps =
    | (CountryFlagBaseProps & {
    width?: undefined
    height?: undefined
})
    | (CountryFlagBaseProps & {
    width: number
    height?: never
})
    | (CountryFlagBaseProps & {
    width?: never
    height: number
})