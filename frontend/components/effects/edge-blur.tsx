import { Platform, StyleSheet, View } from "react-native"
import { BlurView } from "expo-blur"
import { LinearGradient } from "expo-linear-gradient"

type EdgeBlurProps = {
    position: "top" | "bottom"
    color?: string
    dark?: boolean
    height?: number
    intensity?: number
    opacity?: number
    zIndex?: number
}

const blurLayers = [
    { end: 0.3, intensity: 0.52, opacity: 0.42, start: 0 },
    { end: 0.5, intensity: 0.34, opacity: 0.28, start: 0.18 },
    { end: 0.7, intensity: 0.22, opacity: 0.18, start: 0.38 },
    { end: 0.88, intensity: 0.12, opacity: 0.1, start: 0.6 },
    { end: 1, intensity: 0.06, opacity: 0.05, start: 0.78 },
] as const

const primaryGradientLocations = [0, 0.08, 0.2, 0.38, 0.58, 0.78, 1] as const
const featherGradientLocations = [0, 0.24, 0.48, 0.76, 1] as const

export function EdgeBlur({
    position,
    color,
    dark = false,
    height = 90,
    intensity = 35,
    opacity = dark ? 0.28 : 0.2,
    zIndex = 20,
}: EdgeBlurProps) {
    const solidColor = color ?? (dark ? "#000000" : "#FFFFFF")
    const shouldRenderBlur = Platform.OS !== "android"
    const primaryStops = [
        opacity * 0.46,
        opacity * 0.35,
        opacity * 0.25,
        opacity * 0.16,
        opacity * 0.09,
        opacity * 0.04,
        0,
    ]
    const secondaryStops = [
        opacity * 0.08,
        opacity * 0.05,
        opacity * 0.03,
        opacity * 0.015,
        0,
    ]
    const gradientOpacities = position === "top" ? primaryStops : [...primaryStops].reverse()
    const featherOpacities = position === "top" ? secondaryStops : [...secondaryStops].reverse()
    const primaryGradientColors = gradientOpacities.map((stopOpacity) => getRgbaColor(solidColor, stopOpacity)) as [
        string,
        string,
        string,
        string,
        string,
        string,
        string,
    ]
    const featherGradientColors = featherOpacities.map((stopOpacity) => getRgbaColor(solidColor, stopOpacity)) as [
        string,
        string,
        string,
        string,
        string,
    ]

    return (
        <View
            pointerEvents="none"
            style={[
                styles.container,
                {
                    zIndex,
                    height,
                    top: position === "top" ? 0 : undefined,
                    bottom: position === "bottom" ? 0 : undefined,
                },
            ]}
        >
            {shouldRenderBlur ? (
                blurLayers.map((layer, layerIndex) => {
                    const layerHeight = Math.max(1, Math.round(height * (layer.end - layer.start)))
                    const layerOffset = Math.round(height * layer.start)
                    const layerPosition = position === "top" ? { top: layerOffset } : { bottom: layerOffset }

                    return (
                        <BlurView
                            intensity={Math.max(1, Math.round(intensity * layer.intensity))}
                            key={`${position}-${layerIndex}`}
                            style={[
                                styles.blurLayer,
                                layerPosition,
                                {
                                    height: layerHeight,
                                    opacity: layer.opacity,
                                },
                            ]}
                            tint={dark ? "dark" : "light"}
                        />
                    )
                })
            ) : null}
            <LinearGradient
                colors={primaryGradientColors}
                locations={primaryGradientLocations}
                pointerEvents="none"
                style={styles.gradientLayer}
            />
            <LinearGradient
                colors={featherGradientColors}
                locations={featherGradientLocations}
                pointerEvents="none"
                style={styles.gradientLayer}
            />
        </View>
    )
}

function getRgbaColor(color: string, opacity: number) {
    const hexColor = color.trim().replace(/^#/, "")
    const normalizedHex =
        hexColor.length === 3
            ? hexColor
                  .split("")
                  .map((character) => `${character}${character}`)
                  .join("")
            : hexColor
    const hexMatch = normalizedHex.match(/^([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i)

    if (hexMatch) {
        const red = Number.parseInt(hexMatch[1], 16)
        const green = Number.parseInt(hexMatch[2], 16)
        const blue = Number.parseInt(hexMatch[3], 16)
        return `rgba(${red},${green},${blue},${opacity})`
    }

    const rgbMatch = color.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/i)
    if (rgbMatch) {
        return `rgba(${rgbMatch[1]},${rgbMatch[2]},${rgbMatch[3]},${opacity})`
    }

    return color
}

const styles = StyleSheet.create({
    blurLayer: {
        position: "absolute",
        left: 0,
        right: 0,
    },
    container: {
        position: "absolute",
        left: 0,
        right: 0,
        overflow: "hidden",
    },
    gradientLayer: {
        ...StyleSheet.absoluteFillObject,
    },
})
