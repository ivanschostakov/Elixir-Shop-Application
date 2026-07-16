import { Platform } from "react-native"

const darkPage = "#070A0F"
const darkSurface = "#111827"
const darkGray = "#1F2937"
export const archivedPrimaryBlue = "rgb(31, 100, 155)"
export const vividPrimaryBlue = "#0A84FF"
export type ThemeAccentName = "vividBlue" | "archivedBlue" | "teal" | "emerald" | "rose" | "amber" | "blackWhite"

export type ThemeAccentPalette = {
    primary: string
    primaryPressed: string
    primaryMuted: string
    onPrimary: string
}

export const themeAccentPalettes: Record<ThemeAccentName, ThemeAccentPalette> = {
    vividBlue: {
        primary: vividPrimaryBlue,
        primaryPressed: "#0068D9",
        primaryMuted: "#E8F2FF",
        onPrimary: "#FFFFFF",
    },
    archivedBlue: {
        primary: archivedPrimaryBlue,
        primaryPressed: "#174B76",
        primaryMuted: "rgba(31, 100, 155, 0.16)",
        onPrimary: "#FFFFFF",
    },
    teal: {
        primary: "#FFB300",
        primaryPressed: "#D97706",
        primaryMuted: "#FFF0D6",
        onPrimary: "#FFFFFF",
    },
    emerald: {
        primary: "#B0124F",
        primaryPressed: "#8F0E40",
        primaryMuted: "#FFE4EE",
        onPrimary: "#FFFFFF",
    },
    rose: {
        primary: "#8A3FFC",
        primaryPressed: "#6D28D9",
        primaryMuted: "#F1E8FF",
        onPrimary: "#FFFFFF",
    },
    amber: {
        primary: "#2DD66F",
        primaryPressed: "#20A957",
        primaryMuted: "#E5FBEA",
        onPrimary: "#06140A",
    },
    blackWhite: {
        primary: "#0F1115",
        primaryPressed: "#050607",
        primaryMuted: "#EEF1F5",
        onPrimary: "#FFFFFF",
    },
}

export const darkBlackWhiteAccentPalette: ThemeAccentPalette = {
    primary: "#F8FAFC",
    primaryPressed: "#E2E8F0",
    primaryMuted: "rgba(248, 250, 252, 0.18)",
    onPrimary: "#0F1115",
}

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

function colorVariableName(key: string) {
    return `--elixir-color-${key.replace(/[A-Z]/g, (match) => `-${match.toLowerCase()}`)}`
}

export function applyWebThemeColors(themeName: ThemeName) {
    if (Platform.OS !== "web" || typeof document === "undefined") {
        return
    }

    const palette = themeName === "dark" ? darkColors : lightColors
    const rootStyle = document.documentElement.style

    for (const key of Object.keys(lightColors) as (keyof ThemePalette)[]) {
        rootStyle.setProperty(colorVariableName(key), palette[key])
    }

    document.documentElement.style.backgroundColor = palette.pageBackground
    document.body.style.backgroundColor = palette.pageBackground
    document.getElementById("root")?.style.setProperty("background-color", palette.pageBackground)
    rootStyle.colorScheme = themeName
}
