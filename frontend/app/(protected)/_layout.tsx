import { Slot } from "expo-router"

import { ProtectedRoute } from "@/components/navigation/route-guard"

export default function ProtectedLayout() {
    return (
        <ProtectedRoute>
            <Slot />
        </ProtectedRoute>
    )
}
