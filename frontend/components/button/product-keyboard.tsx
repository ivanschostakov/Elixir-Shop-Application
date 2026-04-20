import { Pressable, Text, View } from "react-native"
import { productKeyboardStyles } from "@/components/button/product-keyboard.styles"
import type { ProductKeyboardProps } from "@/components/button/product-keyboard.types"

export default function ProductKeyboard({ productId }: ProductKeyboardProps) {
    return (
        <View style={productKeyboardStyles.container}>
            <Pressable style={productKeyboardStyles.buyButton}>
                <Text style={productKeyboardStyles.buyButtonText}>Купить сейчас</Text>
            </Pressable>

            <Pressable style={productKeyboardStyles.cartButton}>
                <Text style={productKeyboardStyles.cartButtonText}>+ В корзину</Text>
            </Pressable>
        </View>
    )
}
