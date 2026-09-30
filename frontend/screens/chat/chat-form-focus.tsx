import { createContext, useContext } from "react"
import type { TextInput } from "react-native"

const ChatFormFocusContext = createContext<((input: TextInput | null) => void) | null>(null)
export const ChatFormFocusProvider = ChatFormFocusContext.Provider
export const useChatFormFocus = () => useContext(ChatFormFocusContext)
