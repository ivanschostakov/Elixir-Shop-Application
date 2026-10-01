/* global __dirname */
// Run with ESBUILD_PATH and PLAYWRIGHT_PATH pointing to test-only dependencies.
const path = require("node:path")
const fs = require("node:fs")
const http = require("node:http")
const assert = require("node:assert/strict")
const esbuild = require(process.env.ESBUILD_PATH || "esbuild")
const { chromium } = require(process.env.PLAYWRIGHT_PATH || "playwright")
const os = require("node:os")
function chromiumPath() {
    if (process.env.CHROMIUM_PATH) return process.env.CHROMIUM_PATH
    if (fs.existsSync(chromium.executablePath())) return chromium.executablePath()
    const cache = path.join(os.homedir(), "Library/Caches/ms-playwright")
    if (!fs.existsSync(cache)) return undefined
    return fs.readdirSync(cache).filter(name => name.startsWith("chromium_headless_shell-")).sort().reverse().map(name => path.join(cache, name, "chrome-headless-shell-mac-arm64/chrome-headless-shell")).find(candidate => fs.existsSync(candidate))
}
const root = path.resolve(__dirname, "..")
const fixture = path.join(__dirname, "mentor-preview.jsx")
const aliases = ["@/services/api/companion", "@/providers/theme-provider", "@/providers/language-provider", "expo-router"]

async function waitForModeTransition(page) {
    await page.waitForFunction(() => {
        const style = getComputedStyle(document.querySelector(`[data-testid="chat-mode-pane-${window.__mentor.chatMode}"]`))
        const position = style.transform === "none" ? 0 : new DOMMatrixReadOnly(style.transform).m41
        return Number(style.opacity) >= 0.999 && Math.abs(position) < 0.1
    })
}

async function verifyMentorToggleAndModes(browser, url, errors) {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: "no-preference" })
    page.on("pageerror", error => errors.push(error.message))
    await page.goto(`${url}?page=progress`)
    await page.getByText("Прогресс за 7 дней", { exact: true }).waitFor()
    const input = page.getByLabel("Сообщение наставнику", { exact: true })
    const originalInput = await input.elementHandle()
    const originalBackdrop = await page.getByTestId("chat-backdrop").elementHandle()
    const originalHeader = await page.getByTestId("fixture-header").boundingBox()
    const originalBackground = await page.getByTestId("chat-backdrop").boundingBox()
    await input.fill("Несохранённый вопрос ИИ")
    await page.evaluate(() => window.__mentor.loadHistory())
    const headerColors = await page.evaluate(() => ({
        header: getComputedStyle(document.querySelector('[data-testid="fixture-header"]')).backgroundColor,
        switcher: getComputedStyle(document.querySelector('[role="tablist"]')).backgroundColor,
    }))
    assert.equal(headerColors.header, "rgba(0, 0, 0, 0)", "AI header exposes the wallpaper instead of a white panel")
    assert.match(headerColors.switcher, /^rgba\(.+, 0\.88\)$/, "AI switcher uses the same translucent shell as the other modes")
    const hide = page.getByRole("button", { name: "Скрыть наставника", exact: true })
    const wallpaper = await page.getByTestId("chat-backdrop").locator("img").first().getAttribute("src")
    assert.equal(await page.evaluate(() => window.__mentor.shown), true)
    await hide.click()
    await page.getByTestId("fixture-message-history-23").waitFor()
    assert.equal(await page.getByTestId("mentor-workspace").count(), 0)
    assert.equal(await page.getByTestId("fixture-navigation").count(), 0, "Ordinary AI chat hides mentor shortcuts")
    assert.equal(await input.inputValue(), "Несохранённый вопрос ИИ", "Hiding mentor preserves the draft")
    assert.equal(await page.evaluate(() => window.__mentor.shown), false)
    await page.getByRole("button", { name: "Показать наставника", exact: true }).waitFor()
    await page.screenshot({ path: "/tmp/mentor-toggle-ordinary-390.png" })
    await page.getByRole("button", { name: "Показать наставника", exact: true }).click()
    await page.getByText("Прогресс за 7 дней", { exact: true }).waitFor()
    assert.equal(await page.evaluate(() => window.__mentor.mentorPage), "progress", "Showing mentor restores the saved workspace page")
    assert.equal(await page.getByTestId("fixture-navigation").count(), 1)
    assert.equal(await input.inputValue(), "Несохранённый вопрос ИИ")
    await page.screenshot({ path: "/tmp/mentor-toggle-shown-390.png" })

    await page.getByRole("tab", { name: /^Наша группа/ }).click()
    await page.getByText("Наша группа · тестовая страница", { exact: true }).waitFor()
    assert.equal(await page.getByTestId("chat-backdrop").locator("img").first().getAttribute("src"), wallpaper, "Group and AI share the same wallpaper")
    await waitForModeTransition(page)
    assert.equal(await originalInput.evaluate(node => node.isConnected), true, "Switching modes retains the mounted AI composer")
    assert.equal(await originalBackdrop.evaluate(node => node.isConnected), true, "Wallpaper is mounted once")
    assert.deepEqual(await page.getByTestId("fixture-header").boundingBox(), originalHeader, "Header geometry stays fixed between modes")
    assert.deepEqual(await page.getByTestId("chat-backdrop").boundingBox(), originalBackground, "Wallpaper never slides or changes bounds between modes")
    assert.equal(await input.inputValue(), "Несохранённый вопрос ИИ", "A mode transition preserves the existing draft")
    await page.getByRole("tab", { name: "Поддержка", exact: true }).click()
    await page.getByText("Поддержка · тестовая страница", { exact: true }).waitFor()
    assert.equal(await page.getByTestId("chat-backdrop").locator("img").first().getAttribute("src"), wallpaper, "Support and AI share the same wallpaper")
    await waitForModeTransition(page)
    await page.screenshot({ path: "/tmp/mentor-mode-support-390.png" })
    // Dispatch real tab button clicks without Playwright's stability waits so a
    // later switch interrupts an animation that is still in progress.
    for (const name of ["AI", "Наша группа", "Поддержка", "AI"]) {
        await page.getByRole("tab", { name: name === "Наша группа" ? /^Наша группа/ : name, exact: name !== "Наша группа" }).evaluate(element => element.click())
    }
    await page.getByText("Прогресс за 7 дней", { exact: true }).waitFor()
    await waitForModeTransition(page)
    assert.equal(await page.evaluate(() => window.__mentor.chatMode), "ai")
    assert.equal(await input.inputValue(), "Несохранённый вопрос ИИ", "Rapid mode switches do not reset the draft")
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false)
    await page.screenshot({ path: "/tmp/mentor-mode-rapid-390.png" })

    await page.getByRole("button", { name: "Скрыть наставника", exact: true }).click()
    await input.fill("Ответь как обычный ИИ")
    await page.getByLabel("Send message", { exact: true }).click()
    await page.getByTestId("fixture-message-sent-24").waitFor()
    assert.equal(await page.evaluate(() => window.__mentor.store.actions.at(-1).companionEnabled), false, "Ordinary AI message turns off mentor payload through the production mode resolver")
    await page.getByRole("button", { name: "Показать наставника", exact: true }).click()
    await page.getByText(/^Ваш план на сегодня/).waitFor()
    assert.equal(await page.evaluate(() => window.__mentor.mentorPage), "today", "Showing mentor from message history opens today's workspace")
    await page.close()

    const reduced = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: "reduce" })
    reduced.on("pageerror", error => errors.push(error.message))
    await reduced.goto(url)
    await reduced.getByText(/^Ваш план на сегодня/).waitFor()
    await reduced.getByRole("tab", { name: "Поддержка", exact: true }).evaluate(element => element.click())
    await reduced.getByText("Поддержка · тестовая страница", { exact: true }).waitFor()
    const reducedStyle = await reduced.getByTestId("chat-mode-pane-support").evaluate(element => {
        const style = getComputedStyle(element)
        return { opacity: style.opacity, x: style.transform === "none" ? 0 : new DOMMatrixReadOnly(style.transform).m41 }
    })
    assert.equal(reducedStyle.opacity, "1", "Reduce Motion keeps mode content fully visible")
    assert.ok(Math.abs(reducedStyle.x) < 0.1, "Reduce Motion skips the mode slide")
    await reduced.screenshot({ path: "/tmp/mentor-mode-reduced-motion-390.png" })
    await reduced.close()
}

async function verifyQuietLoading(browser, url, errors) {
    for (const initialDelay of [70, 900]) {
        const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
        page.on("pageerror", error => errors.push(error.message))
        await page.addInitScript(() => {
            window.__loadingAppearances = 0
            new MutationObserver(records => {
                for (const record of records) for (const node of record.addedNodes) {
                    if (node.nodeType === 1 && (node.matches('[data-testid="quiet-loading"]') || node.querySelector('[data-testid="quiet-loading"]'))) window.__loadingAppearances++
                }
            }).observe(document, { childList: true, subtree: true })
        })
        await page.goto(`${url}?initialDelay=${initialDelay}`)
        await page.getByTestId("fixture-header").waitFor()
        const header = await page.getByTestId("fixture-header").boundingBox()
        const composer = await page.getByTestId("fixture-composer").boundingBox()
        if (initialDelay > 220) {
            await page.getByTestId("quiet-loading").waitFor()
            assert.equal(await page.getByTestId("mentor-workspace").count(), 0, "Initial chat and mentor appear together instead of partial content")
            await page.getByLabel("Сообщение наставнику", { exact: true }).fill("Вопрос во время загрузки")
            await page.screenshot({ path: "/tmp/mentor-loading-slow-390.png" })
        }
        await page.getByText(/^Ваш план на сегодня/).waitFor()
        assert.equal(await page.getByTestId("quiet-loading").count(), 0)
        assert.equal(await page.evaluate(() => window.__loadingAppearances), initialDelay > 220 ? 1 : 0, "Fast loads never flash a placeholder; slow loads show a single one")
        assert.deepEqual(await page.getByTestId("fixture-header").boundingBox(), header)
        assert.deepEqual(await page.getByTestId("fixture-composer").boundingBox(), composer, "Loading does not move the input or shortcuts")
        if (initialDelay > 220) assert.equal(await page.getByLabel("Сообщение наставнику", { exact: true }).inputValue(), "Вопрос во время загрузки")
        await page.close()
    }
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
    page.on("pageerror", error => errors.push(error.message))
    await page.goto(`${url}?page=progress&dataDelay=400&summaryDelay=1100`)
    await page.getByText("Прогресс за 7 дней", { exact: true }).waitFor()
    await page.getByTestId("quiet-loading").waitFor()
    await page.waitForTimeout(300)
    assert.equal(await page.getByTestId("mentor-weight-chart").count(), 0, "Faster measurements wait for the report summary, avoiding a partial chart")
    assert.equal(await page.getByText("Здесь будет ваш график", { exact: true }).count(), 0, "Loading never masquerades as empty history")
    await page.getByTestId("mentor-weight-chart").waitFor()
    await page.evaluate(() => window.__mentor.setState(structuredClone(window.__mentor.store.state)))
    await page.waitForTimeout(300)
    assert.equal(await page.getByTestId("quiet-loading").count(), 0, "Refreshing the same report retains the chart instead of showing another loader")
    assert.equal(await page.getByTestId("mentor-weight-chart").count(), 1)
    await page.screenshot({ path: "/tmp/mentor-loading-refresh-390.png" })
    await page.close()
}

// A reduced browser viewport verifies the actual production flex shell/input
// under keyboard-sized constraints. It does not emulate UIKit keyboard events.
async function verifyKeyboardSizedViewports(browser, url, errors) {
    for (const [width, fullHeight, availableHeight] of [[390, 844, 444], [320, 568, 310]]) {
        const page = await browser.newPage({ viewport: { width, height: fullHeight } })
        page.on("pageerror", error => errors.push(error.message))
        await page.goto(`${url}?page=workouts`)
        await page.getByRole("button", { name: "Изменить план недели", exact: true }).click()
        const planInput = page.getByLabel("Название плана", { exact: true })
        await planInput.fill("Несохранённый план")
        const originalFormInput = await planInput.elementHandle()
        const lowerField = page.getByLabel("Вес, кг (план)", { exact: true }).last()
        await lowerField.fill("18.5")
        const originalLowerField = await lowerField.elementHandle()
        const wallpaperBounds = await page.getByTestId("chat-backdrop").boundingBox()
        await page.setViewportSize({ width, height: availableHeight })
        assert.deepEqual(await page.getByTestId("chat-backdrop").boundingBox(), wallpaperBounds, "Keyboard-sized windows preserve the wallpaper scale")
        await page.waitForFunction(() => {
            const input = document.activeElement
            const viewport = document.querySelector('[data-testid="fixture-scroll"]').getBoundingClientRect()
            const field = input.getBoundingClientRect()
            return input.getAttribute("aria-label") === "Вес, кг (план)" && field.top >= viewport.top && field.bottom <= viewport.bottom
        })
        assert.equal(await originalLowerField.evaluate(node => node.isConnected && node === document.activeElement), true, "Lower form field keeps native focus while the viewport shrinks")
        assert.equal(await lowerField.inputValue(), "18.5")
        await page.screenshot({ path: `/tmp/mentor-keyboard-focused-field-${width}.png` })
        const composerInput = page.getByLabel("Сообщение наставнику", { exact: true })
        await composerInput.click()
        assert.equal(await originalFormInput.evaluate(node => node.isConnected), true, "Focusing chat must not unmount the unsaved mentor form")
        assert.equal(await planInput.inputValue(), "Несохранённый план")
        await composerInput.fill(Array.from({ length: 16 }, (_, index) => `Строка ${index + 1}: длинное сообщение наставнику`).join("\n"))
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
        const inputBox = await composerInput.boundingBox()
        assert.ok(Math.abs(inputBox.height - 128) <= 1, `Sixteen-line draft must grow to its 128px cap; actual height: ${inputBox.height}px`)
        const shellGeometry = await page.evaluate(() => {
            const box = id => {
                const element = document.querySelector(`[data-testid="${id}"]`)
                const rect = element.getBoundingClientRect()
                return { top: rect.top, bottom: rect.bottom, height: rect.height }
            }
            return { header: box("fixture-header"), scroll: box("fixture-scroll"), composer: box("fixture-composer"), height: innerHeight, overflow: document.documentElement.scrollWidth > innerWidth + 1, pageScroll: window.scrollY }
        })
        assert.ok(shellGeometry.scroll.top >= shellGeometry.header.bottom - 1, "Keyboard-sized viewport keeps history below its header")
        assert.ok(shellGeometry.scroll.bottom <= shellGeometry.composer.top + 1, "Composer occupies layout space rather than covering messages")
        assert.ok(shellGeometry.scroll.height >= 40, "Small portrait keyboard leaves a usable scrolling region even with a long draft")
        assert.ok(shellGeometry.composer.bottom <= shellGeometry.height + 1, "Composer remains inside the available viewport")
        assert.equal(shellGeometry.overflow, false)
        assert.equal(shellGeometry.pageScroll, 0, "The chat scrolls inside its shell rather than moving the document")
        await page.screenshot({ path: `/tmp/mentor-keyboard-form-${width}.png` })

        await page.setViewportSize({ width, height: fullHeight })
        await page.goto(url)
        await page.getByText(/^Ваш план на сегодня/).waitFor()
        await page.evaluate(() => window.__mentor.seedHistory())
        await page.getByTestId("fixture-large-photo").waitFor()
        await composerInput.fill("Уточни состав блюда")
        await page.setViewportSize({ width, height: availableHeight })
        const scroll = page.getByTestId("fixture-scroll")
        await page.waitForFunction(() => {
            const scroll = document.querySelector('[data-testid="fixture-scroll"]')
            return scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 2
        })
        const latest = await page.getByTestId("fixture-message-history-23").boundingBox()
        const composer = await page.getByTestId("fixture-composer").boundingBox()
        assert.ok(latest.y + latest.height <= composer.y + 1, "The latest message can be read above the keyboard dock")
        const atBottom = await scroll.evaluate(element => element.scrollTop)
        assert.ok(atBottom > 1000, "Fixture contains a real long history and large photo")
        const scrollBox = await scroll.boundingBox()
        await page.mouse.move(scrollBox.x + scrollBox.width / 2, scrollBox.y + scrollBox.height / 2)
        await page.mouse.wheel(0, -400)
        await page.waitForFunction(previous => document.querySelector('[data-testid="fixture-scroll"]').scrollTop < previous - 50, atBottom)
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
        const readingOffset = await scroll.evaluate(element => element.scrollTop)
        await page.evaluate(() => window.__mentor.appendMessage())
        await page.getByTestId("fixture-message-incoming-24").waitFor()
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
        assert.ok(Math.abs(await scroll.evaluate(element => element.scrollTop) - readingOffset) < 2, "An incoming answer must not pull the reader away from older messages")
        await scroll.evaluate(element => { element.scrollTop = 0 })
        const first = await page.getByTestId("fixture-message-history-0").boundingBox()
        const header = await page.getByTestId("fixture-header").boundingBox()
        assert.ok(first.y >= header.y + header.height - 1 && first.y < composer.y, "Old messages remain reachable while entering a draft")
        assert.equal(await composerInput.inputValue(), "Уточни состав блюда", "Scrolling history preserves the draft")
        await page.screenshot({ path: `/tmp/mentor-keyboard-history-${width}.png` })
        await scroll.evaluate(element => { element.scrollTop = element.scrollHeight })
        await page.getByLabel("Send message", { exact: true }).click()
        await page.getByTestId("fixture-message-sent-25").waitFor()
        await page.waitForFunction(() => {
            const scroll = document.querySelector('[data-testid="fixture-scroll"]')
            return scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 2
        })
        const sent = await page.getByTestId("fixture-message-sent-25").boundingBox()
        const afterSendDock = await page.getByTestId("fixture-composer").boundingBox()
        assert.ok(sent.y + sent.height <= afterSendDock.y + 1, "Sent message remains reachable above the dock")
        assert.equal(await composerInput.inputValue(), "")
        await page.screenshot({ path: `/tmp/mentor-keyboard-chat-${width}.png` })
        await page.close()
    }
}

async function verifyMentorLanguages(browser, url, errors) {
    const { mentorText } = require("./load-ts.cjs")("i18n/mentor-translations.ts")
    for (const width of [320, 390]) {
        for (const language of ["en", "kz"]) {
            const label = source => mentorText(source, [], language)
            const page = await browser.newPage({ viewport: { width, height: 844 } })
            page.on("pageerror", error => errors.push(error.message))
            page.on("dialog", dialog => dialog.accept())
            await page.goto(`${url}?lang=${language}`)
            await page.getByText(label("Наставник ElixirPeptide"), { exact: true }).waitFor()
            await page.getByText(mentorText("Выполнено {0} из {1}", [2, 5], language), { exact: true }).waitFor()
            const input = page.getByLabel("Сообщение наставнику", { exact: true })
            const originalInput = await input.elementHandle()
            await input.fill("My draft · менің жазбам")
            for (const nextLanguage of ["ru", "kz", "en", language]) {
                await page.evaluate(value => window.__mentor.setLanguage(value), nextLanguage)
                await page.getByText(mentorText("Наставник ElixirPeptide", [], nextLanguage), { exact: true }).waitFor()
                assert.equal(await originalInput.evaluate(node => node.isConnected), true, "Changing language retains the composer")
                assert.equal(await input.inputValue(), "My draft · менің жазбам")
                assert.equal(await page.getByRole("tab", { name: mentorText("Сегодня", [], nextLanguage), exact: true }).count(), 1)
            }
            await page.screenshot({ path: `/tmp/mentor-${language}-today-${width}.png` })
            await page.getByRole("button", { name: label("Прогресс"), exact: true }).click()
            await page.getByText(mentorText("Прогресс за {0} дней", [7], language), { exact: true }).waitFor()
            await page.getByTestId("mentor-weight-chart").waitFor()
            await page.getByTestId("mentor-progress").getByRole("tab", { name: label("Питание"), exact: true }).click()
            await page.getByText(label("Итоги только по сохранённым данным."), { exact: true }).waitFor()
            await page.getByTestId("mentor-progress").getByRole("tab", { name: label("Вес"), exact: true }).click()
            const decimal = await page.evaluate(locale => new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(0.7), language === "en" ? "en-US" : "kk-KZ")
            await page.getByText(`−${decimal} ${language === "en" ? "kg" : "кг"}`, { exact: true }).waitFor()
            await page.screenshot({ path: `/tmp/mentor-${language}-progress-${width}.png` })
            for (const mentorPage of ["nutrition", "workouts", "course", "more", "adjust", "ask"]) {
                await page.evaluate(value => window.__mentor.setMentorPage(value), mentorPage)
                await page.getByTestId("mentor-workspace").waitFor()
                await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)))
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${language} ${mentorPage} overflows at ${width}px`)
                if (mentorPage === "course") {
                    const month = new Date().toLocaleDateString(language === "en" ? "en-US" : "kk-KZ", { month: "long" })
                    assert.ok((await page.getByTestId("mentor-workspace").innerText()).toLowerCase().includes(month.toLowerCase()), "Course calendar uses the selected language")
                }
                if (mentorPage === "workouts") {
                    assert.equal(await page.getByText("Тестовый план", { exact: true }).count(), 1, "Entered plan names are retained")
                    await page.getByRole("button", { name: label("Изменить план недели"), exact: true }).click()
                    const field = page.getByLabel(label("Название плана"), { exact: true })
                    await field.fill("My plan · Менің жоспарым")
                    await page.evaluate(() => window.__mentor.setLanguage("ru"))
                    assert.equal(await page.getByLabel("Название плана", { exact: true }).inputValue(), "My plan · Менің жоспарым")
                    await page.evaluate(value => window.__mentor.setLanguage(value), language)
                    await page.getByRole("button", { name: label("Сохранить план недели"), exact: true }).click()
                    assert.equal(await page.evaluate(() => window.__mentor.store.actions.at(-1).workout_plan.name), "My plan · Менің жоспарым")
                }
            }
            await page.evaluate(() => window.__mentor.setMentorPage("nutrition"))
            await page.getByRole("button", { name: label("Добавить еду"), exact: true }).click()
            await page.getByRole("button", { name: label("Фото еды"), exact: true }).click()
            const prompt = await input.inputValue()
            assert.equal(prompt, label("Хочу записать еду по фото. Уточни порцию и предложи запись для подтверждения."), "Photo instructions follow the selected language")
            await page.close()
        }
    }
}

async function main() {
    const build = await esbuild.build({ absWorkingDir: root, entryPoints: [fixture], bundle: true, write: false, format: "iife", jsx: "automatic", loader: { ".js": "jsx", ".png": "dataurl" }, platform: "browser", define: { "process.env.NODE_ENV": '"development"', __DEV__: "true", global: "globalThis" }, resolveExtensions: [".web.js", ".js", ".tsx", ".ts", ".jsx"], alias: { "react-native": "react-native-web", "react-native-svg": path.join(root, "node_modules/react-native-svg/lib/module/ReactNativeSVG.web.js") }, plugins: [{ name: "test-only-api", setup(build) {
        build.onResolve({ filter: /^(?:@\/|expo-router$)/ }, args => aliases.includes(args.path) ? { path: fixture } : { path: path.join(root, args.path.slice(2)) + (fs.existsSync(path.join(root, args.path.slice(2))) ? "" : fs.existsSync(path.join(root, args.path.slice(2)) + ".tsx") ? ".tsx" : ".ts") })
        build.onLoad({ filter: /\.svg$/ }, args => ({ loader: "jsx", contents: `import React from 'react';export default function Icon(props){return <img alt="" width={props.width} height={props.height} src=${JSON.stringify("data:image/svg+xml;base64," + fs.readFileSync(args.path).toString("base64"))}/>}` }))
    } }] })
    const server = http.createServer((req, res) => { res.setHeader("Content-Type", req.url === "/bundle.js" ? "text/javascript" : "text/html"); res.end(req.url === "/bundle.js" ? build.outputFiles[0].contents : '<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><head><title>Mentor synthetic visual fixture</title><style>html,body,#root{margin:0;height:100%;overflow:hidden}body{-webkit-font-smoothing:antialiased}</style></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>') })
    await new Promise(resolve => server.listen(process.argv.includes("--serve") ? Number(process.env.PORT || 8097) : 0, "127.0.0.1", resolve))
    const url = `http://127.0.0.1:${server.address().port}`
    if (process.argv.includes("--serve")) { console.log(`Synthetic mentor preview: ${url}`); return }
    const browser = await chromium.launch({ headless: true, ...(chromiumPath() ? { executablePath: chromiumPath() } : {}) })
    const errors = []
    try {
        await verifyMentorToggleAndModes(browser, url, errors)
        await verifyQuietLoading(browser, url, errors)
        for (const width of [320, 390, 1280]) {
            const page = await browser.newPage({ viewport: { width, height: 844 } })
            page.on("pageerror", error => { errors.push(error.message); console.error("Browser page error:", error.message) })
            page.on("dialog", dialog => dialog.accept())
            await page.goto(url)
            await page.getByText(/^Ваш план на сегодня/).waitFor()
            assert.equal(await page.getByText(/^Выполнено 2 из 5/).count(), 1)
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false)
            const header = await page.getByTestId("fixture-header").boundingBox()
            const workspace = await page.getByTestId("mentor-workspace").boundingBox()
            assert.ok(workspace.y >= header.y + header.height, "Workspace stays below the fixed header")
            const input = await page.getByLabel("Сообщение наставнику", { exact: true }).boundingBox()
            const shortcutButtons = page.getByTestId("fixture-navigation").getByRole("tab")
            const toggle = page.getByTestId("mentor-mode-shortcut")
            const dock = await page.getByTestId("fixture-composer").boundingBox()
            for (const shortcut of [toggle, ...await shortcutButtons.all()]) {
                const box = await shortcut.boundingBox()
                assert.ok(box.width >= 44 && box.height >= 44, "Icon shortcuts retain finger-sized touch targets")
                assert.ok(box.y >= dock.y && box.y + box.height <= input.y, "All shortcuts sit above the message input")
                assert.ok(box.x >= 0 && box.x + box.width <= width + 1, "All six shortcuts fit the viewport")
                assert.equal(await shortcut.innerText(), "", "Shortcut labels remain accessible without visible text")
            }
            await page.screenshot({ path: `/tmp/mentor-today-${width}.png`, fullPage: true })
            await page.getByRole("button", { name: "Добавить еду", exact: true }).click()
            await page.getByRole("button", { name: "Фото еды", exact: true }).waitFor()
            await page.getByRole("button", { name: "Повторить", exact: true }).click()
            await page.getByRole("button", { name: "Отмена", exact: true }).click()
            assert.equal(await page.evaluate(() => window.__mentor.store.actions.filter(action => action.kind === "entry").length), 0)
            await page.getByRole("button", { name: "В избранное", exact: true }).click()
            await page.getByRole("tab", { name: "Избранное", exact: true }).click()
            await page.getByText("Тестовый обед", { exact: true }).waitFor()
            await page.getByTestId("fixture-navigation").getByRole("tab", { name: "Тренировки", exact: true }).click()
            await page.getByRole("button", { name: "Изменить план недели", exact: true }).click()
            await page.getByLabel("Название плана", { exact: true }).fill("Обновлённый тестовый план")
            await page.getByRole("button", { name: "Сохранить план недели", exact: true }).click()
            assert.equal(await page.evaluate(() => window.__mentor.store.actions.find(action => action.kind === "workout_plan").expected_version), 1)
            await page.getByRole("button", { name: "Начать тренировку", exact: true }).click()
            await page.getByLabel("Вес, кг", { exact: true }).first().fill("20.5")
            await page.getByLabel("Повторения", { exact: true }).first().fill("8")
            await page.getByLabel("Подход 1 выполнен", { exact: true }).check()
            await page.getByRole("button", { name: "Сохранить подходы", exact: true }).click()
            await page.screenshot({ path: `/tmp/mentor-workout-${width}.png` })
            await page.getByRole("button", { name: "Завершить тренировку", exact: true }).click()
            await page.getByText("Завершена", { exact: true }).waitFor()
            const workout = await page.evaluate(() => window.__mentor.store.entries.find(entry => entry.kind === "workout").data.workout)
            assert.equal(workout.status, "completed")
            assert.equal(workout.exercises[0].sets[1].completed, false)
            await page.evaluate(() => window.__mentor.setMentorPage("progress"))
            await page.getByText("Прогресс за 7 дней", { exact: true }).waitFor()
            await page.getByTestId("mentor-weight-chart").locator("polyline").waitFor()
            await page.waitForFunction(() => {
                const svg = document.querySelector('[data-testid="mentor-weight-chart"] svg')
                return svg && Math.abs(svg.viewBox.baseVal.width - svg.getBoundingClientRect().width) < 1
            })
            await page.screenshot({ path: `/tmp/mentor-progress-${width}.png`, fullPage: true })
            assert.ok(await page.locator("svg polyline").count())
            await page.getByTestId("fixture-scroll").evaluate(element => { element.scrollTop = element.scrollHeight })
            await page.getByRole("button", { name: "Добавить данные", exact: true }).scrollIntoViewIfNeeded()
            const addWeight = await page.getByRole("button", { name: "Добавить данные", exact: true }).boundingBox()
            const nav = await page.getByTestId("fixture-navigation").boundingBox()
            assert.ok(addWeight.y + addWeight.height <= nav.y, "Navigation must not cover the final action")
            await page.screenshot({ path: `/tmp/mentor-progress-actions-${width}.png` })
            await page.getByRole("tab", { name: "Питание", exact: true }).first().click()
            await page.getByText("Калории за 7 дней", { exact: true }).waitFor()
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false)
            await page.getByRole("button", { name: "Детали прогресса: замеры, фото и период", exact: true }).click()
            await page.getByRole("tab", { name: "Замеры", exact: true }).click()
            await page.getByRole("button", { name: "Добавить замеры", exact: true }).click()
            await page.getByLabel("Талия, см", { exact: true }).fill("81.5")
            await page.getByRole("button", { name: "Подтвердить замеры", exact: true }).click()
            assert.equal(await page.evaluate(() => window.__mentor.store.entries.find(entry => entry.kind === "measurement").data.measurement.waist_cm), "81.5")
            await page.getByRole("tab", { name: "Фото", exact: true }).click()
            await page.getByRole("button", { name: "Сохранить в прогресс", exact: true }).click()
            await page.getByRole("button", { name: "Отмена", exact: true }).click()
            assert.equal(await page.evaluate(() => window.__mentor.store.entries.filter(entry => entry.kind === "progress_photo").length), 0)
            await page.getByRole("button", { name: "Сохранить в прогресс", exact: true }).click()
            await page.getByRole("button", { name: "Подтвердить сохранение фото", exact: true }).click()
            assert.deepEqual(await page.evaluate(() => window.__mentor.store.entries.find(entry => entry.kind === "progress_photo").data.photo_attachment_ids), [301])
            await page.getByRole("button", { name: "Добавить фото прогресса", exact: true }).click()
            const action = await page.evaluate(() => window.__mentor.store.actions.at(-1))
            assert.equal(action.compose, "photo")
            assert.match(action.text, /^Фото прогресса\./)
            assert.doesNotMatch(action.text, /еду|порци/)
            assert.match(await page.getByLabel("Сообщение наставнику").inputValue(), /^Фото прогресса\./)
            await page.getByLabel("Сообщение наставнику").fill("Покажи мой план на завтра")
            await page.getByLabel("Send message", { exact: true }).click()
            assert.equal(await page.evaluate(() => window.__mentor.store.actions.at(-1).message), "Покажи мой план на завтра")
            assert.equal(await page.getByLabel("Сообщение наставнику").inputValue(), "")
            await page.getByLabel("Record voice message", { exact: true }).click()
            await page.getByText("Тестовая запись голоса", { exact: true }).waitFor()
            await page.getByLabel("Stop voice recording", { exact: true }).click()
            for (const extraPage of ["nutrition", "course", "more", "adjust"]) {
                await page.goto(`${url}?page=${extraPage}`)
                await page.getByTestId("mentor-workspace").waitFor()
                await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
                await page.getByTestId("fixture-scroll").evaluate(element => { element.scrollTop = 0 })
                await page.waitForFunction(() => {
                    const workspace = document.querySelector('[data-testid="mentor-workspace"]').getBoundingClientRect()
                    const header = document.querySelector('[data-testid="fixture-header"]').getBoundingClientRect()
                    return workspace.top >= header.bottom
                })
                await page.screenshot({ path: `/tmp/mentor-${extraPage}-${width}.png` })
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false, `${extraPage} overflows at ${width}px`)
            }
            if (width === 390) {
                await page.goto(`${url}?page=progress`)
                await page.getByRole("button", { name: "Отчёт за 30 дней", exact: true }).click()
                assert.deepEqual(await page.evaluate(() => window.__mentor.store.actions.find(action => action.report)?.report), ["progress", 30])
                await page.goto(url)
                await page.getByText(/^Ваш план на сегодня/).waitFor()
                await page.evaluate(() => {
                    const { store, setState } = window.__mentor
                    store.entries = []
                    store.summary = { ...store.summary, weight_measurements: 0, weight_change_kg: null }
                    const next = structuredClone(store.state)
                    next.entries = []
                    next.mentor.latest_weight = null
                    next.mentor.today.tasks = []
                    next.mentor.today.nutrition = { consumed: { kcal: "0", protein: "0", fat: "0", carbs: "0" }, target: null, remaining: null }
                    store.state = next
                    setState(next)
                })
                await page.getByRole("button", { name: "Дополнить профиль", exact: true }).waitFor()
                await page.getByText("На сегодня нет запланированных событий.", { exact: true }).waitFor()
                await page.getByRole("button", { name: "Прогресс", exact: true }).click()
                await page.getByText("Здесь будет ваш график", { exact: true }).waitFor()
                assert.equal(await page.getByTestId("mentor-weight-chart").count(), 0)
                await page.getByRole("button", { name: "Добавить данные", exact: true }).click()
                assert.equal(await page.evaluate(() => window.__mentor.store.actions.at(-1).editor.page), "weight")
                await page.screenshot({ path: "/tmp/mentor-progress-empty-390.png" })
            }
            await page.close()
        }
        await verifyKeyboardSizedViewports(browser, url, errors)
        await verifyMentorLanguages(browser, url, errors)
        assert.deepEqual(errors, [])
        console.log("English/Kazakh mentor layouts, live language switching, localized calendar and prompts, retained form values, mentor controls, transparent header, ordinary AI toggle, draft preservation, rapid mode transitions, Reduce Motion, and production-shell keyboard-sized viewport regressions passed. Native keyboard events require device verification. Screenshots: /tmp/mentor-{today,progress}-{320,390,1280}.png, /tmp/mentor-toggle-{ordinary,shown}-390.png, /tmp/mentor-mode-{support,rapid,reduced-motion}-390.png and /tmp/mentor-keyboard-{focused-field,form,history,chat}-{320,390}.png")
    } finally { await browser.close(); await new Promise(resolve => server.close(resolve)) }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
