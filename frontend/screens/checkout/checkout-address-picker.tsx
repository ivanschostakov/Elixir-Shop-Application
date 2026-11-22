import { Picker } from "@react-native-picker/picker"

import { useLanguage } from "@/providers/language-provider"
import { ADD_NEW_ADDRESS_VALUE, NO_ADDRESS_VALUE } from "@/screens/checkout/checkout-screen.constants"
import type { StyleProp, TextStyle } from "react-native"

type AddressValue = number | typeof ADD_NEW_ADDRESS_VALUE | typeof NO_ADDRESS_VALUE

export function CheckoutAddressPicker({ addresses, selectedValue, onSelect, style }: {
    addresses: readonly { id: number; full_address: string }[]
    selectedValue: AddressValue
    onSelect: (value: number | typeof ADD_NEW_ADDRESS_VALUE) => void
    style?: StyleProp<TextStyle>
}) {
    const { t } = useLanguage()
    return <Picker accessibilityLabel={t("checkout.addressSectionTitle")} selectedValue={selectedValue}
        onValueChange={value => {
            if (value === ADD_NEW_ADDRESS_VALUE) onSelect(value)
            else if (typeof value === "number" && addresses.some(address => address.id === value)) onSelect(value)
        }} style={style}>
        <Picker.Item label={t("checkout.openDelivery")} value={NO_ADDRESS_VALUE} />
        <Picker.Item label={t("checkout.addressAddNew")} value={ADD_NEW_ADDRESS_VALUE} />
        {addresses.map(address => <Picker.Item key={address.id} label={address.full_address} value={address.id} />)}
    </Picker>
}
