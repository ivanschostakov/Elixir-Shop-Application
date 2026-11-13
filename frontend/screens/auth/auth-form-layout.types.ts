import type { ReactNode, RefObject } from "react"
import type { ScrollView } from "react-native"

export type AuthFormLayoutProps = {
    children: ReactNode
    error?: string | null
    scrollRef?: RefObject<ScrollView | null>
    title: string
    backAction?: { label: string; onPress: () => void; disabled?: boolean }
}
