import { AppStack } from "@/components/navigation/app-stack"

import { GuestRoute } from "@/components/navigation/route-guard"

export default function GuestLayout() {
    return (
        <GuestRoute>
            <AppStack />
        </GuestRoute>
    )
}
