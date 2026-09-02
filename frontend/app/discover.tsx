import DiscoverScreen from "@/screens/discover/discover-screen"
import { CatalogRoute } from "@/components/navigation/route-guard"

export default function Discover() {
    return <CatalogRoute><DiscoverScreen /></CatalogRoute>
}
