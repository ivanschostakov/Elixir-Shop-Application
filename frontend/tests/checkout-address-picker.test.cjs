const assert = require("node:assert/strict")
const test = require("node:test")
const load = require("./load-ts.cjs")

test("the first address can be added from an unselected placeholder, before saved addresses", () => {
    const constants = load("screens/checkout/checkout-screen.constants.ts")
    const { NO_ADDRESS_VALUE, ADD_NEW_ADDRESS_VALUE } = constants
    const choices = []
    const { CheckoutAddressPicker } = load("screens/checkout/checkout-address-picker.tsx", {
        "@react-native-picker/picker": { Picker: Object.assign(() => {}, { Item: "Item" }) },
        "@/providers/language-provider": { useLanguage: () => ({ t: key => key }) },
        "@/screens/checkout/checkout-screen.constants": constants,
    })
    const render = addresses => CheckoutAddressPicker({ addresses, selectedValue: NO_ADDRESS_VALUE, onSelect: value => choices.push(value) })
    const empty = render([])
    assert.equal(empty.props.selectedValue, NO_ADDRESS_VALUE)
    const values = node => node.props.children.flat(Infinity).filter(Boolean).map(item => item.props.value)
    assert.deepEqual(values(empty), [NO_ADDRESS_VALUE, ADD_NEW_ADDRESS_VALUE])
    empty.props.onValueChange(NO_ADDRESS_VALUE)
    assert.deepEqual(choices, [])
    empty.props.onValueChange(ADD_NEW_ADDRESS_VALUE)
    assert.deepEqual(choices, [ADD_NEW_ADDRESS_VALUE])
    const saved = render([{ id: 7, full_address: "Saved address" }])
    assert.deepEqual(values(saved), [NO_ADDRESS_VALUE, ADD_NEW_ADDRESS_VALUE, 7])
    saved.props.onValueChange(7)
    saved.props.onValueChange("not-an-address")
    assert.deepEqual(choices, [ADD_NEW_ADDRESS_VALUE, 7])
})
