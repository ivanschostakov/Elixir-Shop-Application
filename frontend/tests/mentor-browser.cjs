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
        await page.setViewportSize({ width, height: availableHeight })
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
        assert.deepEqual(errors, [])
        console.log("Mentor mobile/desktop controls and production-shell keyboard-sized viewport regressions passed. Native keyboard events require device verification. Screenshots: /tmp/mentor-{today,progress}-{320,390,1280}.png and /tmp/mentor-keyboard-{focused-field,form,history,chat}-{320,390}.png")
    } finally { await browser.close(); await new Promise(resolve => server.close(resolve)) }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
