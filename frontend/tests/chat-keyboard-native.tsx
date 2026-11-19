// Isolated native layout fixture. Never imported by app routes; no account/API access.
import React, { useEffect, useRef, useState } from "react"
import { AppRegistry, Keyboard, ScrollView, StyleSheet, Text, TextInput, View, useWindowDimensions } from "react-native"
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context"
import { ChatKeyboardLayout } from "../screens/chat/chat-keyboard-layout"
import { ChatComposer } from "../screens/chat/chat-composer"
import { LanguageProvider } from "../providers/language-provider"
import { ChatKeyboardPane, ChatMessageScrollView, ChatComposerDock } from "../screens/chat/chat-keyboard-motion"
import { NativeChatModeControl, NativeChatAction } from "../screens/chat/native-chat-controls"
import { ChatTopicTitle } from "../screens/chat/chat-topic-title"
import { ThemeProvider } from "../providers/theme-provider"
import { KeyboardProvider, useReanimatedKeyboardAnimation } from "react-native-keyboard-controller"
import Reanimated, { measure as measureOnUI, runOnJS, useAnimatedRef, useFrameCallback, useSharedValue } from "react-native-reanimated"
import { ChatModePane, ChatModeTransition } from "../screens/chat/chat-mode-transition"
import { useChatScroll } from "../hooks/chat/use-chat-scroll"

const endpoint = "http://127.0.0.1:8103"
const initialMessages = Array.from({ length: 28 }, (_, index) => `Сообщение ${index + 1}. Проверка прокрутки длинной переписки наставника.`)
type Box = { x: number; y: number; width: number; height: number }
const measure = (view: View | TextInput | null): Promise<Box | null> => new Promise(resolve => {
    if (!view) return resolve(null)
    view.measureInWindow((x, y, width, height) => resolve({ x, y, width, height }))
})

function Fixture() {
    const insets = useSafeAreaInsets()
    const { height: screenHeight } = useWindowDimensions()
    const { height: keyboardHeight, progress } = useReanimatedKeyboardAnimation()
    const measuredInput = useAnimatedRef<View>()
    const samples = useSharedValue<{ time: number; keyboard: number; inputBottom: number }[]>([])
    const moving = useSharedValue(false)
    const reportMotion = (frames: typeof samples.value) => {
        void fetch(`${endpoint}/metrics`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stage: "motion-frames", screenHeight, frames }) }).catch(() => undefined)
    }
    useFrameCallback(frame => {
        const animating = progress.value > 0 && progress.value < 1
        if (!animating && !moving.value) return
        const box = measureOnUI(measuredInput)
        if (box) samples.value = [...samples.value, { time: frame.timestamp, keyboard: keyboardHeight.value, inputBottom: box.pageY + box.height }]
        if (!animating) {
            runOnJS(reportMotion)(samples.value)
            samples.value = []
        }
        moving.value = animating
    })
    const [messages, setMessages] = useState(initialMessages)
    const [draft, setDraft] = useState("")
    const [topicTitle, setTopicTitle] = useState(false)
    const [stage, setStage] = useState("initial")
    const [mode, setMode] = useState<"ai" | "support">("ai")
    const input = useRef<TextInput | null>(null)
    const scroll = useRef<ScrollView | null>(null)
    const header = useRef<View | null>(null)
    const viewport = useRef<View | null>(null)
    const composer = useRef<View | null>(null)
    const scrollOffset = useRef(0)
    const keyboardY = useRef<number | null>(null)
    const historyOffset = useRef(0)
    const inputContentSize = useRef({ width: 0, height: 0 })
    const scrolling = useChatScroll(scroll, null)
    const report = useRef<(name: string) => Promise<void>>(async () => {})
    report.current = async name => {
        const [headerBox, viewportBox, composerBox, inputBox] = await Promise.all([
            measure(header.current), measure(viewport.current), measure(composer.current), measure(input.current),
        ])
        const result = { stage: name, fixtureStage: stage, mode, header: headerBox, viewport: viewportBox, composer: composerBox, input: inputBox, inputContentSize: inputContentSize.current, draftLength: draft.length, keyboardY: keyboardY.current, scrollOffset: scrollOffset.current, historyOffset: historyOffset.current }
        console.log("NATIVE_KEYBOARD_FIXTURE", JSON.stringify(result))
        void fetch(`${endpoint}/metrics`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(result) }).catch(() => undefined)
    }
    useEffect(() => {
        const show = Keyboard.addListener("keyboardDidShow", event => { keyboardY.current = event.endCoordinates.screenY; void report.current("keyboard-did-show") })
        const hide = Keyboard.addListener("keyboardDidHide", () => { keyboardY.current = null })
        return () => { show.remove(); hide.remove() }
    }, [])
    useEffect(() => {
        const timers = [
            setTimeout(() => { void report.current("before-mode-transition") }, 200),
            setTimeout(() => { setMode("support") }, 400),
            setTimeout(() => { setMode("ai") }, 900),
            setTimeout(() => { void report.current("after-mode-transition") }, 1300),
            setTimeout(() => { setStage("keyboard"); input.current?.focus() }, 1800),
            setTimeout(() => { void report.current("single-line") }, 3500),
            setTimeout(() => { setStage("multiline"); setDraft(Array.from({ length: 12 }, (_, i) => `Строка ${i + 1}: многострочный ввод`).join("\n")) }, 5000),
            setTimeout(() => { void report.current("multiline") }, 6500),
            setTimeout(() => { setStage("read-history"); scrolling.onScrollBeginDrag(); scroll.current?.scrollTo({ y: 240, animated: false }) }, 8000),
            setTimeout(() => { historyOffset.current = scrollOffset.current; setMessages(current => [...current, "Новое сообщение во время чтения истории."]) }, 9500),
            setTimeout(() => { void report.current("history-after-incoming"); setStage("closed-topic"); Keyboard.dismiss(); setDraft(""); setTopicTitle(true) }, 11000),
            setTimeout(() => { void report.current("closed-topic"); setStage("complete") }, 15000),
        ]
        return () => timers.forEach(clearTimeout)
    // One deterministic scenario per fixture launch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
    return <ChatKeyboardLayout style={styles.screen}>
        <View ref={header} collapsable={false} style={[styles.header, { paddingTop: insets.top + 8, position: "absolute", top: 0, left: 0, right: 0, zIndex: 12 }]}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            {NativeChatAction ? <NativeChatAction action="back" dark={false} label="Назад" onAction={() => {}} style={{ width: 44, height: 44 }} /> : null}
            {topicTitle ? <ChatTopicTitle title="Вопросы к производителю, новости" /> : NativeChatModeControl ? <NativeChatModeControl dark={false} labels={["AI", "Группа", "Поддержка"]} badges={["", "99+", ""]} selectedIndex={mode === "ai" ? 0 : 2} onSelect={({ nativeEvent }) => setMode(nativeEvent.index === 0 ? "ai" : "support")} style={{ flex: 1, height: 44 }} /> : <Text style={styles.title}>Наставник ElixirPeptide</Text>}
            </View>
        </View>
        <ChatModeTransition mode={mode}>
        <ChatModePane mode="ai" active={mode === "ai"}>
        <ChatKeyboardPane>
        <View ref={viewport} collapsable={false} style={styles.body}>
            <ChatMessageScrollView ref={scroll} style={styles.scroll} contentContainerStyle={[styles.messages, { paddingTop: insets.top + 64, paddingBottom: 8 }]}
                automaticallyAdjustKeyboardInsets={false} contentInsetAdjustmentBehavior="never"
                keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive" scrollEventThrottle={16}
                onLayout={scrolling.onLayout} onContentSizeChange={scrolling.onContentSizeChange}
                onScrollBeginDrag={scrolling.onScrollBeginDrag}
                onScroll={event => { scrollOffset.current = event.nativeEvent.contentOffset.y; scrolling.onScroll(event) }}>
                <>{messages.map((message, i) => <View key={i} style={[styles.bubble, i % 2 ? styles.userBubble : null]}><Text style={styles.message}>{message}</Text></View>)}<View style={[styles.bubble, styles.userBubble]}><View style={styles.photo}><Text>Фото: тестовый блок 240 × 250</Text></View><Text style={styles.message}>Хочу записать еду по фото.</Text></View></>
            </ChatMessageScrollView>
        </View>
        <ChatComposerDock ref={composer} style={[styles.composer, { position: "absolute", bottom: 0, left: 0, right: 0, paddingBottom: Math.max(8, insets.bottom) }]}>

            {topicTitle ? <View style={{ alignSelf: "center", backgroundColor: "#b91c1c", borderRadius: 16, paddingHorizontal: 14, paddingVertical: 7 }}><Text style={{ color: "white" }}>Тема закрыта</Text></View> : <Reanimated.View ref={measuredInput} collapsable={false}><ChatComposer inputRef={input} value={draft} onChangeText={setDraft} placeholder="Сообщение поддержке" hasContent={Boolean(draft)} onAttachment={() => {}} onAction={() => { setMessages(current => [...current, draft || "Тестовое сообщение"]); setDraft(""); scrolling.followLatest() }} /></Reanimated.View>}
        </ChatComposerDock>
        </ChatKeyboardPane>
        </ChatModePane>
        <ChatModePane mode="support" active={mode === "support"}><View style={styles.screen}><Text style={{ marginTop: insets.top + 70 }}>Локальная тестовая поддержка</Text></View></ChatModePane>
        </ChatModeTransition>
    </ChatKeyboardLayout>
}

const styles = StyleSheet.create({
    screen: { flex: 1, backgroundColor: "#e9fbef" }, modeToggle: { height: 34, flexDirection: "row", alignItems: "center", justifyContent: "space-between" }, header: { backgroundColor: "transparent", paddingHorizontal: 12, paddingBottom: 10, flexShrink: 0 }, title: { fontSize: 18, fontWeight: "600", color: "#1d6248" }, status: { fontSize: 11, color: "#64766e" }, navigation: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 8 }, body: { flex: 1, minHeight: 0 }, scroll: { flex: 1, minHeight: 0 }, messages: { flexGrow: 1, justifyContent: "flex-end", padding: 10, gap: 8 }, bubble: { backgroundColor: "#fff", borderRadius: 15, padding: 12, maxWidth: "85%", alignSelf: "flex-start" }, userBubble: { backgroundColor: "#e1ffc7", alignSelf: "flex-end" }, message: { fontSize: 16, lineHeight: 22 }, photo: { width: 240, height: 250, backgroundColor: "#aec8bc", alignItems: "center", justifyContent: "center", borderRadius: 10 }, composer: { flexShrink: 0, paddingHorizontal: 8, paddingTop: 4 }, row: { flexDirection: "row", alignItems: "flex-end", gap: 7 }, circle: { height: 40, width: 40, borderRadius: 20, backgroundColor: "#fff", alignItems: "center", justifyContent: "center" }, inputWrap: { flex: 1, minWidth: 0, minHeight: 40, maxHeight: 128, flexDirection: "row", alignItems: "flex-end", borderRadius: 20, backgroundColor: "#fff", overflow: "hidden", paddingHorizontal: 12 }, input: { flex: 1, minWidth: 0, minHeight: 40, maxHeight: 128, fontSize: 17, lineHeight: 22, paddingVertical: 9, paddingHorizontal: 0 }, form: { backgroundColor: "white", padding: 12, gap: 18, borderRadius: 16 }, field: { minHeight: 48, backgroundColor: "#f0f5f2", padding: 12, borderRadius: 8, fontSize: 16 }, action: { backgroundColor: "#88c4a6", padding: 16, borderRadius: 12 },
})

function NativeKeyboardFixture() { return <ThemeProvider><SafeAreaProvider><KeyboardProvider preload={false}><LanguageProvider><Fixture /></LanguageProvider></KeyboardProvider></SafeAreaProvider></ThemeProvider> }
AppRegistry.registerComponent("main", () => NativeKeyboardFixture)
