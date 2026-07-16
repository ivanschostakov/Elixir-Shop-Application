import { Pressable, Text, View } from "react-native"
import { createProductKeyboardStyles } from "@/components/button/product-keyboard.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import type { ProductKeyboardProps } from "@/components/button/product-keyboard.types"

export default function ProductKeyboard({ productId }: ProductKeyboardProps) {
    const productKeyboardStyles = useThemeStyles(createProductKeyboardStyles)
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
