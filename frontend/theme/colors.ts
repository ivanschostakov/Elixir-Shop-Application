import { DynamicColorIOS, Platform } from "react-native"

const darkPage = "#070A0F"
const darkSurface = "#111827"
const darkGray = "#1F2937"
export const archivedPrimaryBlue = "rgb(31, 100, 155)"

export const lightColors = {
    background: "#FFFFFF",
    pageBackground: "#F3F5F8",
    surface: "#FFFFFF",
    surfaceElevated: "#F8FAFC",
    surfaceMuted: "#EEF4FA",
    surfaceSoft: "#FBFCFE",
    fieldBackground: "#F8FBFD",
    pressedSurface: "#F3F8FB",
    surfaceOverlay: "rgba(255,255,255,0.96)",
    surfaceOverlaySoft: "rgba(255,255,255,0.88)",
    veil: "rgba(255,255,255,0.42)",
    veilSoft: "rgba(255,255,255,0.2)",
    railTile: "#FFFFFF",
    text: "#111827",
    stateText: "#526476",
    mutedText: "#6B7280",
    border: "#E5E7EB",
    borderSoft: "#D7E4EE",
    divider: "#E8EFF5",
    primary: "#0A84FF",
    primaryPressed: "#096FE0",
    primaryMuted: "#EAF3FF",
    favorite: "#EF4444",
    discountedPrice: "#18E56B",
    danger: "#BE123C",
    dangerMuted: "#FFF4F6",
    success: "#0F6A37",
    successMuted: "#E4F6EA",
    warning: "#B45309",
    warningMuted: "#FEF3C7",
    onPrimary: "#FFFFFF",
}

export type ThemeName = "light" | "dark"
export type ThemePalette = typeof lightColors

export const darkColors: ThemePalette = {
    background: darkSurface,
    pageBackground: darkPage,
    surface: darkSurface,
    surfaceElevated: darkGray,
    surfaceMuted: darkGray,
    surfaceSoft: darkPage,
    fieldBackground: darkGray,
    pressedSurface: darkGray,
    surfaceOverlay: darkSurface,
    surfaceOverlaySoft: darkSurface,
    veil: "rgba(7,10,15,0.54)",
    veilSoft: "rgba(7,10,15,0.34)",
    railTile: darkSurface,
    text: "#F8FAFC",
    stateText: "#A7B1C2",
    mutedText: "#A7B1C2",
    border: "#283446",
    borderSoft: "#2D3A4E",
    divider: "#263246",
    primary: "#0A84FF",
    primaryPressed: "#006FE0",
    primaryMuted: "rgba(10, 132, 255, 0.18)",
    favorite: "#EF4444",
    discountedPrice: "#4ADE80",
    danger: "#FB7185",
    dangerMuted: "rgba(251, 113, 133, 0.16)",
    success: "#4ADE80",
    successMuted: "rgba(74, 222, 128, 0.14)",
    warning: "#FBBF24",
    warningMuted: "rgba(251, 191, 36, 0.14)",
    onPrimary: "#FFFFFF",
}

const dynamicColor = (light: string, dark: string) => {
    if (Platform.OS !== "ios") {
        return light
    }

    return DynamicColorIOS({ light, dark }) as unknown as string
}

export const colors = Object.fromEntries(
    Object.keys(lightColors).map((key) => {
        const paletteKey = key as keyof ThemePalette
        return [paletteKey, dynamicColor(lightColors[paletteKey], darkColors[paletteKey])]
    }),
) as ThemePalette
