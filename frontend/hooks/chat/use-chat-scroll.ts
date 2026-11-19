import { useCallback, useEffect, useLayoutEffect, useRef, type RefObject } from "react"
import type { NativeScrollEvent, NativeSyntheticEvent, ScrollView, TextInput } from "react-native"
import { CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD } from "@/screens/chat/chat-screen.constants"

/** Follow the latest message only while the reader is already at the bottom. */
export function useChatScroll(
    scrollRef: RefObject<ScrollView | null>,
    workspacePage: string | null,
    onFollowingChange?: (following: boolean) => void,
    { top = 0, bottom = 0 }: { top?: number; bottom?: number } = {},
) {
    const page = useRef(workspacePage)
    const following = useRef(true)
    const resetting = useRef(false)
    const frame = useRef<number | null>(null)
    const focusedField = useRef<TextInput | null>(null)
    const scrollOffset = useRef(0)
    const focusFrame = useRef<number | null>(null)
    const focusMeasurement = useRef(0)
    const revealField = useCallback(() => {
        const measurement = ++focusMeasurement.current
        if (focusFrame.current != null) cancelAnimationFrame(focusFrame.current)
        focusFrame.current = null
        if (!page.current || !focusedField.current) return
        focusFrame.current = requestAnimationFrame(() => {
            focusFrame.current = null
            const input = focusedField.current
            if (!page.current || !input?.isFocused()) return
            scrollRef.current?.getNativeScrollRef()?.measureInWindow((_x, viewportY, _width, viewportHeight) => {
                input.measureInWindow((_inputX, inputY, _inputWidth, inputHeight) => {
                    if (measurement !== focusMeasurement.current || focusedField.current !== input || !input.isFocused() || viewportHeight <= top + bottom) return
                    const below = inputY + inputHeight - (viewportY + viewportHeight - bottom - 12)
                    const above = inputY - (viewportY + top + 12)
                    const delta = below > 0 ? below : above < 0 ? above : 0
                    if (delta) scrollRef.current?.scrollTo({ y: Math.max(0, scrollOffset.current + delta), animated: false })
                })
            })
        })
    }, [bottom, scrollRef, top])
    useLayoutEffect(() => { revealField() }, [revealField])
    const cancel = useCallback(() => {
        if (frame.current != null) cancelAnimationFrame(frame.current)
        frame.current = null
        resetting.current = false
    }, [])
    const settle = useCallback(() => {
        if (page.current || !following.current) return
        cancel()
        resetting.current = true
        frame.current = requestAnimationFrame(() => {
            scrollRef.current?.scrollToEnd({ animated: false })
            frame.current = requestAnimationFrame(() => { frame.current = null; resetting.current = false })
        })
    }, [cancel, scrollRef])
    useLayoutEffect(() => {
        page.current = workspacePage
        focusedField.current = null
        focusMeasurement.current++
        following.current = true
        onFollowingChange?.(true)
        if (workspacePage) {
            scrollOffset.current = 0
            scrollRef.current?.scrollTo({ y: 0, animated: false })
        } else {
            settle()
        }
        return cancel
    }, [workspacePage, scrollRef, settle, cancel, onFollowingChange])
    useEffect(() => () => { cancel(); if (focusFrame.current != null) cancelAnimationFrame(focusFrame.current) }, [cancel])
    const onScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
        scrollOffset.current = event.nativeEvent.contentOffset.y
        if (page.current || resetting.current) return
        const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent
        const nextFollowing = contentSize.height - contentOffset.y - layoutMeasurement.height <= CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD
        if (following.current === nextFollowing) return
        following.current = nextFollowing
        onFollowingChange?.(nextFollowing)
    }, [onFollowingChange])
    const followLatest = useCallback((animated = false) => {
        if (animated && !page.current) {
            cancel()
            scrollRef.current?.scrollToEnd({ animated: true })
            return
        }
        following.current = true
        onFollowingChange?.(true)
        settle()
    }, [cancel, onFollowingChange, scrollRef, settle])
    const onFieldFocus = useCallback((input: TextInput | null) => { focusedField.current = input; revealField() }, [revealField])
    const onLayout = useCallback(() => { settle(); revealField() }, [settle, revealField])
    return { onScroll, onScrollBeginDrag: cancel, onContentSizeChange: settle, onLayout, followLatest, onFieldFocus }
}
