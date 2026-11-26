import { BlurView, type BlurViewProps } from "expo-blur"
import { Platform } from "react-native"

type Props = Omit<BlurViewProps, "experimentalBlurMethod"> & { androidBlur?: boolean }
/** Android surfaces opt in to live backdrop blur. */
export function AppBlurSurface({ androidBlur = false, ...props }: Props) {
    return <BlurView {...props} experimentalBlurMethod={Platform.OS === "android" && androidBlur ? "dimezisBlurView" : "none"} />
}
