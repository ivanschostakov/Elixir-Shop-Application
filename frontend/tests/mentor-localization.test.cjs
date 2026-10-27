/* global __dirname */
const { test } = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const ts = require("typescript")
const loadTs = require("./load-ts.cjs")
const language = loadTs("i18n/translations.ts")
const { mentorText, mentorLocale, mentorDateLabel, mentorDateTimeLabel, mentorTranslations } = loadTs("i18n/mentor-translations.ts", { "@/i18n/translations": language })
const data = loadTs("screens/chat/mentor-data.ts", { "@/i18n/mentor-translations": { mentorText } })
const dates = loadTs("screens/chat/companion-timezones.ts", { "@/i18n/mentor-translations": { mentorText, mentorLocale, mentorDateTimeLabel } })

test("mentor follows language changes without freezing module labels or altering entered values", () => {
    try {
        for (const [locale, title, goal, waist] of [
            ["ru", "Наставник ElixirPeptide", "Снижение веса", "Талия, см"],
            ["en", "ElixirPeptide Mentor", "Weight loss", "Waist, cm"],
            ["kz", "ElixirPeptide тәлімгері", "Салмақ азайту", "Бел, см"],
        ]) {
            language.setTranslationLanguage(locale)
            assert.equal(mentorText("Наставник ElixirPeptide"), title)
            assert.equal(data.goalLabels.weight_loss, goal)
            assert.equal(data.measurementLabels.waist_cm, waist)
            const meal = { kind: "meal", data: { kind: "meal", name: "Сегодня", note: "Моя запись {0}", occurred_at: "2026-09-29T12:00:00Z", nutrition: { kcal: "450" } } }
            assert.deepEqual(data.repeatMeal(meal, meal.data.occurred_at), { ...meal.data, favorite: false })
            assert.equal(mentorText("{0} кг", ["Моя запись {0}"]), `Моя запись {0} ${locale === "en" ? "kg" : "кг"}`)
        }
    } finally { language.setTranslationLanguage("ru") }
})

test("both mentor catalogs cover all interface phrases and preserve every interpolation", () => {
    for (const [source, translations] of Object.entries(mentorTranslations)) {
        for (const locale of ["en", "kz"]) {
            assert.ok(translations[locale]?.trim(), `${locale}: ${source}`)
            assert.deepEqual([...source.matchAll(/\{\d+\}/g)].map(v => v[0]).sort(), [...translations[locale].matchAll(/\{\d+\}/g)].map(v => v[0]).sort(), `${locale}: ${source}`)
            if (locale === "en") assert.doesNotMatch(translations[locale], /[А-Яа-яЁё]/, source)
        }
    }
    for (const file of ["mentor.tsx", "mentor-progress.tsx", "mentor-workouts.tsx", "mentor-photos.tsx", "mentor-data.ts", "companion.tsx", "companion-dialogue.tsx", "companion-timezones.ts"]) {
        const filename = path.join(__dirname, "../screens/chat", file)
        const source = ts.createSourceFile(filename, fs.readFileSync(filename, "utf8"), ts.ScriptTarget.Latest, true)
        const visit = node => {
            if (ts.isCallExpression(node) && node.expression.getText(source) === "mt" && ts.isStringLiteral(node.arguments[0])) {
                assert.ok(Object.hasOwn(mentorTranslations, node.arguments[0].text.trim()), `${file}: missing ${node.arguments[0].text}`)
            }
            ts.forEachChild(node, visit)
        }
        visit(source)
    }
})

test("phone time remains the same instant while dates, numbers and validation errors change language", () => {
    const value = "2026-09-29T18:42:00Z", clock = "UTC+05:45|0|2026-09-29"
    try {
        for (const locale of ["ru", "en", "kz"]) {
            language.setTranslationLanguage(locale)
            assert.equal(dates.companionCalendarDay(value, clock), "2026-09-30")
            assert.equal(dates.formatCompanionDate(value, clock), mentorDateTimeLabel(new Date("2026-09-30T00:27:00Z"), "UTC"))
            assert.equal(dates.localEntryTimestamp(dates.localDateTime(value), value), value)
            assert.throws(() => dates.localEntryTimestamp("invalid", value), { message: mentorText("Укажите дату и время в формате ГГГГ-ММ-ДД ЧЧ:ММ") })
        }
        assert.equal(mentorLocale("kz"), "kk-KZ")
        assert.equal(mentorDateLabel(new Date(2026, 8, 29), { day: "numeric", month: "long" }, "kz"), "29 қыркүйек")
        assert.equal(mentorDateTimeLabel(new Date("2026-09-30T00:27:00Z"), "UTC", "kz"), "30.09.2026, 00:27:00")
        assert.equal(mentorText("Выполнено {0} из {1}", [2, 5], "en"), "Completed 2 of 5")
        assert.equal(mentorText("Выполнено {0} из {1}", [2, 5], "kz"), "5 тапсырманың 2 орындалды")
    } finally { language.setTranslationLanguage("ru") }
})
