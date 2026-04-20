import { Slot } from "expo-router"

import { GuestRoute } from "@/components/navigation/route-guard"

export default function GuestLayout() {
    return (
        <GuestRoute>
            <Slot />
        </GuestRoute>
    )
}
