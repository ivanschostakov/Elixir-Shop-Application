import { AppStack } from "@/components/navigation/app-stack"

import { ProtectedRoute } from "@/components/navigation/route-guard"

export default function ProtectedLayout() {
    return (
        <ProtectedRoute>
            <AppStack />
        </ProtectedRoute>
    )
}
