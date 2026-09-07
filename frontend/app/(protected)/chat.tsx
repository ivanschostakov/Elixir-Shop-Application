import ChatScreen from "@/screens/chat/chat-screen"
import IosSupportRouteScreen from "@/screens/chat/ios-support-route-screen"
import { Platform } from "react-native"

export default function ChatRoute() {
    return Platform.OS === "ios" ? <IosSupportRouteScreen /> : <ChatScreen />
}
