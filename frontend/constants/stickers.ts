import type { ImageSourcePropType } from "react-native"
import type { AnimationObject } from "lottie-react-native"

export type StickerConfig =
    | {
        kind: "image"
        source: ImageSourcePropType
    }
    | {
        kind: "lottie"
        source: AnimationObject
    }

export const STICKERS: Record<
    "cartEmpty" | "favoritesEmpty" | "noProducts" | "cherryCongrats" | "orderHistoryEmpty",
    StickerConfig
> = {
    cartEmpty: {
        kind: "lottie",
        source: require("../assets/stickers/rabby-shop.json") as AnimationObject,
    },
    favoritesEmpty: {
        kind: "lottie",
        source: require("../assets/stickers/utya-fav.json") as AnimationObject,
    },
    noProducts: {
        kind: "image",
        source: require("../assets/stickers/utya-shop.gif"),
    },
    cherryCongrats: {
        kind: "lottie",
        source: require("../assets/stickers/cherry-congrats.json") as AnimationObject,
    },
    orderHistoryEmpty: {
        kind: "lottie",
        source: require("../assets/stickers/utya-shop.json") as AnimationObject,
    },
}
