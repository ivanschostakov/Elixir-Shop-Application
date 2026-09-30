const assert = require("node:assert/strict")
const { readFileSync } = require("node:fs")
const { join } = require("node:path")
const test = require("node:test")
const loadTs = require("./load-ts.cjs")

const source = file => readFileSync(join(__dirname, "..", file), "utf8")
const jsxRuntime = { jsx: (type, props) => ({ type, props }) }

test("iOS opens the shared home after authentication loads", () => {
    let isReady = false
    const Home = () => null
    const Loading = () => null
    const { default: Index } = loadTs("app/index.tsx", {
        "react/jsx-runtime": jsxRuntime,
        "react-native": { Platform: { OS: "ios" } },
        "@/components/navigation/auth-loading-screen": { default: Loading },
        "@/screens/home/home-screen": { default: Home },
        "@/providers/auth-provider": { useAuth: () => ({ isReady }) },
    })
    assert.equal(Index().type, Loading)
    isReady = true
    assert.equal(Index().type, Home)
})

test("iOS chat uses the shared consent-aware chat screen", () => {
    const Chat = () => null
    const { default: Route } = loadTs("app/(protected)/chat.tsx", {
        "react/jsx-runtime": jsxRuntime,
        "react-native": { Platform: { OS: "ios" } },
        "@/screens/chat/chat-screen": { default: Chat },
    })
    assert.equal(Route().type, Chat)
    assert.match(source("screens/chat/chat-screen.tsx"), /useAiChatEntryConsent/)
})

test("navigation no longer redirects or hides commerce and chat modes on iOS", () => {
    const shell = source("components/navigation/app-shell.tsx")
    assert.doesNotMatch(shell, /isRestrictedIosRoute|isIosRestrictedRoute|IOS_PRIMARY_APP_ROUTES/)
    assert.match(shell, /primaryAppRoutes = PRIMARY_APP_ROUTES/)
    for (const file of [
        "components/footer/bottom-nav-template.tsx",
        "screens/chat/chat-mode-switcher.tsx",
        "screens/profile/profile-screen.tsx",
        "screens/profile/profile-history-screen.tsx",
        "screens/chat/mentor.tsx",
    ]) {
        assert.doesNotMatch(source(file), /Platform\.OS\s*[!=]==\s*"ios"/, file)
    }
    const footer = source("components/footer/bottom-nav-template.tsx")
    assert.match(footer, /key: ROUTES.discover/)
    assert.match(footer, /key: ROUTES.basket/)
    assert.match(footer, /!isAuthenticated && isAccountRequiredRoute/)
})
