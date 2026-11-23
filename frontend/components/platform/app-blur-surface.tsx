import { BlurView, type BlurViewProps } from "expo-blur"
import { Platform } from "react-native"

type Props = Omit<BlurViewProps, "experimentalBlurMethod"> & { androidBlur?: boolean }
/** Expensive Android blur is enabled only for surfaces that previously used it. */
export function AppBlurSurface({ androidBlur = false, ...props }: Props) {
    return <BlurView {...props} experimentalBlurMethod={Platform.OS === "android" && androidBlur ? "dimezisBlurView" : "none"} />
}
