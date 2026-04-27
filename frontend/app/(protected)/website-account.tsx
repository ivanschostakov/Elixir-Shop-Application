import { Redirect } from "expo-router"

import { ROUTES } from "@/constants/routes"

export default function WebsiteAccountRoute() {
    return <Redirect href={ROUTES.profile} />
}
