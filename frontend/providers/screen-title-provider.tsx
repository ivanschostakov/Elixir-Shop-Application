import { useState } from "react"

import {
    ScreenTitleContext,
    type ScreenTitleProviderProps,
} from "@/providers/screen-title-provider.context"

export function ScreenTitleProvider({ children }: ScreenTitleProviderProps) {
    const [titleOverride, setTitleOverride] = useState<string | null>(null)

    return (
        <ScreenTitleContext.Provider value={{ titleOverride, setTitleOverride }}>
            {children}
        </ScreenTitleContext.Provider>
    )
}

export { useScreenTitle } from "@/providers/screen-title-provider.context"
