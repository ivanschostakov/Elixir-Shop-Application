import { useCallback, useEffect, useLayoutEffect, useRef, type RefObject } from "react"
import type { NativeScrollEvent, NativeSyntheticEvent, ScrollView, TextInput } from "react-native"
import { CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD } from "@/screens/chat/chat-screen.constants"

/** Follow the latest message only while the reader is already at the bottom. */
export function useChatScroll(scrollRef: RefObject<ScrollView | null>, workspacePage: string | null) {
    const page = useRef(workspacePage)
    const following = useRef(true)
    const resetting = useRef(false)
    const frame = useRef<number | null>(null)
    const pendingTop = useRef(!!workspacePage)
    const focusedField = useRef<TextInput | null>(null)
    const scrollOffset = useRef(0)
    const focusFrame = useRef<number | null>(null)
    const revealField = useCallback(() => {
        if (focusFrame.current != null) cancelAnimationFrame(focusFrame.current)
        focusFrame.current = requestAnimationFrame(() => {
            focusFrame.current = null
            const input = focusedField.current
            if (!page.current || !input?.isFocused()) return
            scrollRef.current?.getNativeScrollRef()?.measureInWindow((_x, viewportY, _width, viewportHeight) => {
                input.measureInWindow((_inputX, inputY, _inputWidth, inputHeight) => {
                    if (focusedField.current !== input || !input.isFocused() || viewportHeight <= 0) return
                    const below = inputY + inputHeight - (viewportY + viewportHeight - 12)
                    const above = inputY - (viewportY + 12)
                    const delta = below > 0 ? below : above < 0 ? above : 0
                    if (delta) scrollRef.current?.scrollTo({ y: Math.max(0, scrollOffset.current + delta), animated: false })
                })
            })
        })
    }, [scrollRef])
    const cancel = useCallback(() => {
        if (frame.current != null) cancelAnimationFrame(frame.current)
        frame.current = null
        resetting.current = false
    }, [])
    const settle = useCallback(() => {
        if (page.current ? !pendingTop.current : !following.current) return
        cancel()
        resetting.current = true
        frame.current = requestAnimationFrame(() => {
            if (page.current) {
                scrollRef.current?.scrollTo({ y: 0, animated: false })
                pendingTop.current = false
            } else {
                scrollRef.current?.scrollToEnd({ animated: false })
            }
            frame.current = requestAnimationFrame(() => { frame.current = null; resetting.current = false })
        })
    }, [cancel, scrollRef])
    useLayoutEffect(() => {
        page.current = workspacePage
        pendingTop.current = !!workspacePage
        following.current = true
        settle()
        return cancel
    }, [workspacePage, settle, cancel])
    useEffect(() => () => { cancel(); if (focusFrame.current != null) cancelAnimationFrame(focusFrame.current) }, [cancel])
    const onScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
        scrollOffset.current = event.nativeEvent.contentOffset.y
        if (page.current || resetting.current) return
        const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent
        following.current = contentSize.height - contentOffset.y - layoutMeasurement.height <= CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD
    }, [])
    const followLatest = useCallback(() => { following.current = true; settle() }, [settle])
    const onFieldFocus = useCallback((input: TextInput | null) => { focusedField.current = input; if (input) revealField() }, [revealField])
    const onLayout = useCallback(() => { settle(); revealField() }, [settle, revealField])
    return { onScroll, onScrollBeginDrag: cancel, onContentSizeChange: onLayout, onLayout, followLatest, onFieldFocus }
}
