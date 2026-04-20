import { createContext, useContext, useState } from "react"
import type { ReactNode } from "react"

type ScreenTitleContextValue = {
    setTitleOverride: (title: string | null) => void
    titleOverride: string | null
}

const ScreenTitleContext = createContext<ScreenTitleContextValue | null>(null)

export function ScreenTitleProvider({ children }: { children: ReactNode }) {
    const [titleOverride, setTitleOverride] = useState<string | null>(null)

    return (
        <ScreenTitleContext.Provider value={{ titleOverride, setTitleOverride }}>
            {children}
        </ScreenTitleContext.Provider>
    )
}

export function useScreenTitle() {
    const context = useContext(ScreenTitleContext)

    if (!context) {
        throw new Error("useScreenTitle must be used within a ScreenTitleProvider")
    }

    return context
}
