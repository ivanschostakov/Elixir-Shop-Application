const assert = require("node:assert/strict")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

function setup() {
    const state = []
    let cursor = 0
    const requests = []
    let rejectSend = false
    const inbox = { active: null, previous: [], total_unread: 0 }
    const jsx = (type, props) => ({ type, props })
    const runtime = { jsx, jsxs: jsx, Fragment: "Fragment" }
    const react = {
        useState: initial => {
            const index = cursor++
            if (!(index in state)) state[index] = initial
            return [state[index], value => { state[index] = typeof value === "function" ? value(state[index]) : value }]
        },
        useEffect: () => {}, useCallback: fn => fn, useRef: value => ({ current: value }),
    }
    const native = Object.fromEntries(["Image", "ImageBackground", "KeyboardAvoidingView", "Pressable", "RefreshControl", "ScrollView", "Text", "View"].map(name => [name, name]))
    const support = {
        closePrevious: () => {}, openPrevious: async () => {}, refresh: async () => {},
        conversation: null, error: null, loading: false, refreshing: false, sending: false,
        createConversation: async payload => { requests.push({ kind: "create", payload }); if (rejectSend) throw Error("Offline") },
        sendMessage: async payload => { requests.push({ kind: "send", payload }); if (rejectSend) throw Error("Offline") },
    }
    const { SupportChatScreen } = loadTs("screens/chat/support-chat-screen.tsx", {
        react, "react/jsx-runtime": runtime,
        "react-native": { ...native, Platform: { OS: "ios" }, Alert: { alert: () => {} }, Keyboard: { dismiss: () => {} } },
        "expo-camera": { useCameraPermissions: () => [{ granted: true }, async () => ({ granted: true })] },
        "expo-audio": {
            RecordingPresets: { HIGH_QUALITY: {} },
            setAudioModeAsync: async () => {},
            useAudioRecorder: () => ({ prepareToRecordAsync: async () => {}, record: () => {}, stop: async () => {}, uri: "file:///voice.m4a" }),
            useAudioRecorderState: () => ({ durationMillis: 1000 }),
        },
        "@/screens/chat/chat-recording-permission": { requestChatRecordingPermission: async () => true },
        "@/services/api/ai-chat": { transcribeMyAiChatVoice: async () => ({ text: "Spoken order question" }) },
        "expo-image-picker": { launchImageLibraryAsync: async () => ({ canceled: false, assets: [{ uri: "file:///photo.jpg", fileName: "photo.jpg" }] }) },
        "expo-router": { useRouter: () => ({ push: () => {} }) },
        "react-native-safe-area-context": { useSafeAreaInsets: () => ({ top: 59, bottom: 34 }) },
        "@/screens/chat/chat-keyboard-motion": { ChatKeyboardPane: "Pane", ChatMessageScrollView: "Messages", ChatComposerDock: "Dock" },
        "@/screens/chat/chat-edge-blur": { ChatEdgeBlur: "Blur" },
        "@/constants/routes": { ROUTES: { discover: "/discover" } },
        "@/hooks/chat/use-chat-scroll": { useChatScroll: () => ({}) },
        "@/hooks/chat/use-support-chat": { useSupportChat: () => ({ ...support, inbox, conversation: inbox.active }) },
        "@/hooks/use-theme-styles": { useThemeStyles: () => ({}) },
        "@/providers/language-provider": { useLanguage: () => ({ t: key => key }) },
        "@/providers/theme-provider": { useTheme: () => ({ isDark: false, themeName: "light", palette: {} }) },
        "@/services/api/constants": { API_BASE_URL: "https://example.test/api" },
        "@/services/auth/session": { getAuthTokens: () => null },
        "@/screens/chat/chat-attachments": {
            createAttachmentFromImagePickerAsset: asset => ({ uri: asset.uri, fileName: asset.fileName, mimeType: "image/jpeg" }),
            formatVoiceDuration: () => "0:01", getVoiceRecordingFilename: () => "voice.m4a", getVoiceRecordingMimeType: () => "audio/mp4",
        },
        "@/screens/chat/chat-screen.attachments": { AttachmentSheet: "AttachmentSheet", QueuedAttachmentStrip: "QueuedAttachments" },
        "@/screens/chat/chat-screen.constants": { CHAT_BACKGROUND_LIGHT: "light", CHAT_BACKGROUND_DARK: "dark" },
        "@/screens/chat/chat-composer": { ChatComposer: "Composer" },
        "@/screens/chat/native-chat-controls": { NativeChatMenu: null },
        "@/screens/chat/chat-screen.styles": { createChatScreenStyles: () => ({}) },
        "@/screens/chat/support-chat-screen.styles": { createSupportChatStyles: () => ({}) },
        "@/components/ui/quiet-loading": { QuietLoading: "Loading" },
        "@/theme/spacing": { spacing: { sm: 8, md: 16 } },
        "@/utils/uuid": { createUuid: () => "stable-message-id" },
    })
    const render = () => { cursor = 0; return SupportChatScreen({ active: true, onUnreadChange: () => {}, requestedConversationId: null }) }
    function find(tree, type) {
        if (!tree || typeof tree !== "object") return undefined
        if (Array.isArray(tree)) return tree.map(item => find(item, type)).find(Boolean)
        if (tree.type === type) return tree
        return find(tree.props?.children, type)
    }
    return { requests, inbox, find, render, failSend: () => { rejectSend = true } }
}
const flush = () => new Promise(resolve => setImmediate(resolve))

test("support opens with text composer and creates a conversation without another service", async () => {
    const h = setup()
    const composer = h.find(h.render(), "Composer")
    assert.equal(composer.props.placeholder, "chat.supportInputPlaceholder")
    assert.equal(composer.props.hasContent, false)
    composer.props.onChangeText("Question about order")
    h.find(h.render(), "Composer").props.onAction()
    await flush()
    assert.deepEqual(h.requests, [{ kind: "create", payload: { client_message_id: "stable-message-id", subject: "Question about order", message: "Question about order" } }])
    assert.equal(h.find(h.render(), "Composer").props.value, "")
})

test("support records voice and sends the transcription to support", async () => {
    const h = setup()
    h.find(h.render(), "Composer").props.onAction()
    await flush()
    const recording = h.find(h.render(), "Composer")
    assert.equal(recording.props.recording, true)
    recording.props.onAction()
    await flush()
    assert.deepEqual(h.requests, [{ kind: "create", payload: { client_message_id: "stable-message-id", subject: "Spoken order question", message: "Spoken order question" } }])
    assert.equal(h.find(h.render(), "Composer").props.recording, false)
})

test("support keeps the draft after a send failure", async () => {
    const h = setup()
    h.failSend()
    h.find(h.render(), "Composer").props.onChangeText("Keep this draft")
    h.find(h.render(), "Composer").props.onAction()
    await flush()
    assert.equal(h.find(h.render(), "Composer").props.value, "Keep this draft")
})

test("support attaches selected photos to its active conversation", async () => {
    const h = setup()
    h.inbox.active = { id: 12, status: "open", messages: [], customer_unread_count: 0 }
    h.find(h.render(), "Composer").props.onAttachment()
    h.find(h.render(), "AttachmentSheet").props.onOpenNativeGallery()
    await flush()
    const composer = h.find(h.render(), "Composer")
    assert.equal(composer.props.hasContent, true)
    composer.props.onAction()
    await flush()
    assert.deepEqual(h.requests, [{ kind: "send", payload: { clientMessageId: "stable-message-id", message: "", attachments: [{ uri: "file:///photo.jpg", fileName: "photo.jpg", mimeType: "image/jpeg" }] } }])
})
