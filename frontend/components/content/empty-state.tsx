import { Platform } from "react-native"

import { EmptyState as NativeEmptyState } from "@/components/content/empty-state.native"
import type { EmptyStateProps } from "@/components/content/empty-state.types"
import { EmptyState as WebEmptyState } from "@/components/content/empty-state.web"

export function EmptyState(props: EmptyStateProps) {
    if (Platform.OS === "web") {
        return <WebEmptyState {...props} />
    }

    return <NativeEmptyState {...props} />
}
