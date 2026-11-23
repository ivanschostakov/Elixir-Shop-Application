import { AppBlurSurface as BlurView } from "@/components/platform/app-blur-surface"
import type { StyleProp, ViewStyle } from "react-native"

import { NativeComposerMaterial } from "@/components/platform/native-controls"

export function AppEdgeMaterial({ dark, topEdge = false, style }: {
    dark: boolean
    topEdge?: boolean
    style: StyleProp<ViewStyle>
}) {
    if (NativeComposerMaterial) {
        return <NativeComposerMaterial dark={dark} topEdge={topEdge} pointerEvents="none" style={style} />
    }

    return <BlurView
        intensity={18}
        pointerEvents="none"
        style={style}
        tint={dark ? "systemUltraThinMaterialDark" : "systemUltraThinMaterialLight"}
    />
}
