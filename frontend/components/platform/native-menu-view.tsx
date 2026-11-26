import { Platform } from "react-native"

export const MenuView: typeof import("@react-native-menu/menu").MenuView | null = Platform.OS === "web"
    ? null
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    : require("@react-native-menu/menu").MenuView
