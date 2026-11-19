/* global __dirname */
const assert = require("node:assert/strict")
const { execFileSync } = require("node:child_process")
const { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } = require("node:fs")
const { tmpdir } = require("node:os")
const { dirname, join } = require("node:path")
const test = require("node:test")
const ts = require("typescript")

const platformDirectory = { darwin: "osx-bin", linux: "linux64-bin", win32: "win64-bin" }[process.platform]
const hermes = platformDirectory && join(dirname(require.resolve("react-native/package.json")), "sdks/hermesc", platformDirectory, process.platform === "win32" ? "hermes.exe" : "hermes")

test("course and meal cards render in Hermes without NumberFormat.formatToParts", { skip: !hermes || !existsSync(hermes) }, t => {
    const path = join(__dirname, "../screens/chat/companion-dialogue.tsx")
    const source = ts.createSourceFile(path, readFileSync(path, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const functions = ["displayNumber", "shortTime", "localDateParts", "dateRange", "scheduleLabel", "CoursePlanDetails", "NutritionMetric", "EntryDetails"]
    const body = functions.map(name => {
        const declaration = source.statements.find(node => ts.isFunctionDeclaration(node) && node.name?.text === name)
        assert.ok(declaration, `Missing card renderer: ${name}`)
        return declaration.getText(source)
    }).join("\n")
    const compiled = ts.transpileModule(body, {
        compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2018, jsx: ts.JsxEmit.ReactJSX },
        fileName: "card-renderers.tsx",
    }).outputText
    const directory = mkdtempSync(join(tmpdir(), "elixir-card-hermes-"))
    t.after(() => rmSync(directory, { recursive: true, force: true }))
    const script = join(directory, "cards.js")
    writeFileSync(script, `
var exports = {};
var language = 'ru-RU';
var View = 'View', Text = 'Text', styles = {}, weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
var units = { mg: 'mg' };
function useLanguage() {}
function useTheme() { return { palette: {} }; }
function mentorLocale() { return language; }
function mentorDateLabel(value, options) { return new Intl.DateTimeFormat(language, options).format(value); }
function formatCompanionDate(value) { return new Date(value).toISOString(); }
function mt(text, args) { return text.replace(/\\{(\\d+)\\}/g, function(_, index) { return String(args[index]); }); }
function jsx(type, props) { return typeof type === 'function' ? type(props) : { type: type, props: props }; }
function require(name) {
    if (name === 'react/jsx-runtime') return { jsx: jsx, jsxs: jsx };
    throw new Error('Unexpected dependency: ' + name);
}
function text(node) {
    if (node == null || typeof node === 'boolean') return '';
    if (Array.isArray(node)) return node.map(text).join(' ');
    if (typeof node === 'object') return text(node.props.children);
    return String(node);
}
function equal(actual, expected) { if (actual !== expected) throw new Error(actual + ' != ' + expected); }
function contains(actual, expected) { if (actual.indexOf(expected) < 0) throw new Error('Missing rendered text: ' + expected); }
// This API is absent in the Hermes shipped with React Native 0.81.5.
// Keep exercising that runtime limitation when a future Hermes adds it.
Intl.NumberFormat.prototype.formatToParts = undefined;
${compiled}
for (var locale of ['ru-RU', 'en-US', 'kk-KZ']) {
    language = locale;
    var decimal = locale === 'en-US' ? '.' : ',';
    equal(displayNumber('0.250'), '0' + decimal + '250');
    equal(displayNumber(0.125), '0' + decimal + '125');
    equal(displayNumber('12345.000000001'), '12345' + decimal + '000000001');
    var course = CoursePlanDetails({ plan: { name: 'Saved course', items: [{ name: 'Saved item', stages: [{ start_date: '2026-11-18', end_date: '2026-11-25', amount: '0.250', unit: 'mg', weekdays: [], interval_days: 1, times: ['08:00:00'] }] }] }, recommended: true, reminders: true });
    contains(text(course), 'Saved course');
    contains(text(course), '0' + decimal + '250');
    contains(text(course), '08:00');
    var meal = EntryDetails({ entry: { kind: 'meal', name: 'Saved meal', occurred_at: '2026-11-18T12:00:00Z', nutrition: { kcal: '450.50', protein: '25.125', fat: '10.25', carbs: '60.50' } }, clock: 'UTC|0|2026-11-18' });
    contains(text(meal), 'Saved meal');
    contains(text(meal), '25' + decimal + '125');
}
print('Hermes course and meal card rendering passed in ru/en/kz');
`)
    const output = execFileSync(hermes, [script], { encoding: "utf8", timeout: 15000 })
    assert.match(output, /Hermes course and meal card rendering passed in ru\/en\/kz/)
})
