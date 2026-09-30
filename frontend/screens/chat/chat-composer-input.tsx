import { useEffect, useState, type Ref } from "react"
import { Platform, TextInput, type TextInputProps } from "react-native"

export const CHAT_INPUT_MIN_HEIGHT = 40
export const CHAT_INPUT_MAX_HEIGHT = 128
export function chatInputHeight(contentHeight: number) {
    return Math.max(CHAT_INPUT_MIN_HEIGHT, Math.min(CHAT_INPUT_MAX_HEIGHT, Math.ceil(contentHeight)))
}

/** Grow with the draft, then scroll inside the input instead of displacing the chat. */
export function ChatComposerInput({ inputRef, style, value, onContentSizeChange, ...props }: TextInputProps & { inputRef?: Ref<TextInput> }) {
    const [height, setHeight] = useState(CHAT_INPUT_MIN_HEIGHT)
    useEffect(() => { if (!value) setHeight(CHAT_INPUT_MIN_HEIGHT) }, [value])
    return <TextInput
        {...props}
        ref={inputRef}
        value={value}
        multiline
        textAlignVertical="top"
        scrollEnabled
        onContentSizeChange={event => {
            if (Platform.OS === "web") setHeight(chatInputHeight(event.nativeEvent.contentSize.height))
            onContentSizeChange?.(event)
        }}
        // Native text inputs already measure their text through Yoga. Fixing their
        // height can prevent Fabric from emitting a new content-size event when
        // a controlled draft changes, leaving the composer stuck at one line.
        style={[style, { height: Platform.OS === "web" ? height : undefined, minHeight: CHAT_INPUT_MIN_HEIGHT, maxHeight: CHAT_INPUT_MAX_HEIGHT }]}
    />
}
