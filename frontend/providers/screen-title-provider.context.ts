import type { ReactNode } from "react"
import { createContext, useContext } from "react"

export type ScreenTitleContextValue = {
    setTitleOverride: (title: string | null) => void
    titleOverride: string | null
}

export type ScreenTitleProviderProps = {
    children: ReactNode
}

export const ScreenTitleContext = createContext<ScreenTitleContextValue | null>(null)

export function useScreenTitle() {
    const context = useContext(ScreenTitleContext)

    if (!context) {
        throw new Error("useScreenTitle must be used within a ScreenTitleProvider")
    }

    return context
}
