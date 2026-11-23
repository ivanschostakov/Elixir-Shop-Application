import { useEffect, useRef, useState } from "react"
import { ActivityIndicator, Image, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import type { useCompanion } from "@/screens/chat/companion"
import { MentorHomeHeader } from "@/screens/chat/mentor-home"
import { mentorHomeNumber as number } from "@/screens/chat/mentor-home-data"
import { mealLabel } from "@/screens/chat/mentor-meals-data"
import { MentorQuestionIcon } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { requestKey } from "@/services/api/companion"
import { askNutritionHelp, type FoodEstimate, type FoodSuggestion } from "@/services/api/companion-food"
import { AiConsentDeclinedError } from "@/services/api/ai-data-consent"
import { getErrorMessage } from "@/utils/errors"

export function DishPhoto({ recipe, large = false }: { recipe: FoodSuggestion; large?: boolean }) {
    const colors = useMentorPalette(), [failedUrl, setFailedUrl] = useState<string | null>(null)
    const photoUrl = recipe.image?.url
    return <View style={[styles.photo, large && styles.hero, { backgroundColor: colors.soft }]}>
        {photoUrl && photoUrl !== failedUrl ? <Image accessibilityLabel={mt("Фото похожего блюда: {0}", [recipe.name])} source={{ uri: photoUrl, headers: { "User-Agent": "ElixirNutrition/1.0 (recipe photograph display)" } }} resizeMode="cover" onError={() => setFailedUrl(photoUrl)} style={StyleSheet.absoluteFill} /> : <MentorQuestionIcon name="food" size={large ? 52 : 38} color={colors.green} />}
    </View>
}

export function MentorFoodSuggestions({ controller: c, shown, onClose }: { controller: ReturnType<typeof useCompanion>; shown: boolean; onClose: () => void }) {
    useLanguage()
    const colors = useMentorPalette()
    const [result, setResult] = useState<FoodEstimate | null>(null), [selected, setSelected] = useState<FoodSuggestion | null>(null)
    const [busy, setBusy] = useState(true), [error, setError] = useState("")
    const scroll = useRef<ScrollView>(null)
    const request = useRef<string | null>(null), pending = useRef<Promise<FoodEstimate> | null>(null), alive = useRef(true), handoff = useRef(false)
    const load = () => {
        if (!request.current) request.current = requestKey()
        if (!pending.current) pending.current = askNutritionHelp("suggest", mt("Подберите блюда на следующий приём пищи с учётом моего дневника и оставшихся КБЖУ."), null, request.current)
        setBusy(true); setError("")
        void pending.current.then(value => {
            if (!alive.current) return
            if (!value.suggestions?.length) { setResult(null); setError(mt("Не удалось подобрать блюда. Попробуйте ещё раз.")); request.current = null; return }
            setResult(value)
        }).catch(e => { if (alive.current) { if (e instanceof AiConsentDeclinedError) onClose(); else setError(getErrorMessage(e)) } }).finally(() => { pending.current = null; if (alive.current) setBusy(false) })
    }
    const latestLoad = useRef(load); latestLoad.current = load
    useEffect(() => { alive.current = true; if (shown) latestLoad.current(); return () => { alive.current = false } }, [shown])
    useEffect(() => { scroll.current?.scrollTo({ y: 0, animated: false }) }, [selected])
    const ask = () => {
        if (handoff.current) return
        handoff.current = true
        const question = selected ? mt("Хочу приготовить «{0}»: {1}. Ингредиенты: {2}. Примерно {3} ккал, белки {4} г, жиры {5} г, углеводы {6} г на порцию. Подойдёт ли это мне на следующий приём пищи с учётом оставшихся КБЖУ и моих предпочтений?", [selected.name, selected.portion, selected.ingredients.join("; "), number(selected.nutrition.kcal), number(selected.nutrition.protein), number(selected.nutrition.fat), number(selected.nutrition.carbs)]) : mt("Что мне лучше съесть на следующий приём пищи с учётом моего дневника, оставшихся КБЖУ и предпочтений?")
        c.askMentor(question)
    }
    const context = result?.next_meal
    return <>
        <MentorHomeHeader title={selected ? mt("Рецепт") : mt("Что поесть?")} onBack={() => selected ? setSelected(null) : onClose()} />
        <ScrollView ref={scroll} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.body}>
            {selected ? <>
                <DishPhoto key={selected.name} recipe={selected} large />
                <Text accessibilityRole="header" style={[styles.title, { color: colors.text }]}>{selected.name}</Text>
                <Text style={[styles.caption, { color: colors.muted }]}>{selected.portion} · {mt("{0} мин", [selected.minutes])}</Text>
                <View style={[styles.macros, { backgroundColor: colors.soft }]}>{(["kcal", "protein", "fat", "carbs"] as const).map((key, i) => <View key={key} style={styles.macro}><Text style={[styles.macroValue, { color: colors.text }]}>{number(selected.nutrition[key])}</Text><Text style={[styles.macroLabel, { color: colors.muted }]}>{[mt("ккал"), mt("Белки, г"), mt("Жиры, г"), mt("Углеводы, г")][i]}</Text></View>)}</View>
                <Text style={[styles.copy, { color: colors.text }]}>{selected.description}</Text>
                <Text style={[styles.heading, { color: colors.text }]}>{mt("Ингредиенты")}</Text>
                {selected.ingredients.map((item, i) => <View key={i} style={[styles.ingredient, { borderBottomColor: colors.border }]}><View style={[styles.dot, { backgroundColor: colors.green }]} /><Text style={[styles.copy, { color: colors.text, flex: 1 }]}>{item}</Text></View>)}
                <Text style={[styles.heading, { color: colors.text, marginTop: 8 }]}>{mt("Как приготовить")}</Text>
                {selected.steps.map((step, i) => <View key={i} style={styles.step}><View style={[styles.stepNumber, { backgroundColor: colors.soft }]}><Text style={[styles.stepText, { color: colors.green }]}>{i + 1}</Text></View><Text style={[styles.copy, { color: colors.text, flex: 1 }]}>{step}</Text></View>)}
                {selected.image ? <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(selected.image!.source_url).catch(() => setError(mt("Не удалось открыть ссылку")))}><Text style={[styles.credit, { color: colors.muted }]}>{mt("Фото похожего блюда")} · {selected.image.author || "Wikimedia Commons"} · {selected.image.license}</Text></Pressable> : null}
            </> : <>
                <Text accessibilityRole="header" style={[styles.title, { color: colors.text }]}>{busy ? mt("Подбираем для вас") : context ? mealLabel(context.meal_type) : mt("На следующий приём пищи")}</Text>
                {busy ? <><Text style={[styles.caption, { color: colors.muted }]}>{mt("Учитываем дневник, КБЖУ и ваши предпочтения")}</Text><ActivityIndicator color={colors.green} style={{ padding: 12 }} />{[0, 1].map(i => <View key={i} style={[styles.skeleton, { backgroundColor: colors.soft }]} />)}</> : null}
                {!busy && context?.budget ? <View style={[styles.budget, { backgroundColor: colors.soft }]}><Text style={[styles.budgetValue, { color: colors.green }]}>{Number(context.budget.kcal) > 0 ? mt("Около {0} ккал на приём", [number(context.budget.kcal)]) : mt("Дневной ориентир набран")}</Text><Text style={[styles.caption, { color: colors.muted }]}>{mt("Осталось на сегодня: {0} ккал", [number(context.remaining?.kcal)])}</Text></View> : null}
                {!busy ? result?.suggestions?.map(recipe => <Pressable key={recipe.name} accessibilityRole="button" accessibilityLabel={mt("Открыть рецепт: {0}", [recipe.name])} onPress={() => setSelected(recipe)} style={({ pressed }) => [styles.card, { backgroundColor: colors.soft, opacity: pressed ? 0.8 : 1 }]}>
                    <DishPhoto recipe={recipe} />
                    <View style={styles.cardText}><Text style={[styles.dishName, { color: colors.text }]}>{recipe.name}</Text><Text style={[styles.caption, { color: colors.muted }]}>{recipe.portion} · {mt("{0} мин", [recipe.minutes])}</Text><Text style={[styles.calories, { color: colors.green }]}>{number(recipe.nutrition.kcal)} {mt("ккал")}</Text><Text style={[styles.caption, { color: colors.text }]}>{recipe.description}</Text><View style={styles.recipeLink}><Text style={[styles.linkText, { color: colors.green }]}>{mt("Посмотреть рецепт")}</Text><MentorQuestionIcon name="chevronRight" color={colors.green} size={18} /></View></View>
                </Pressable>) : null}
            </>}
            {error ? <View style={styles.error}><Text accessibilityRole="alert" style={[styles.copy, { color: colors.text }]}>{error}</Text>{!selected ? <Pressable accessibilityRole="button" accessibilityLabel={mt("Попробовать ещё раз")} disabled={busy} onPress={load}><Text style={[styles.linkText, { color: colors.green }]}>{mt("Попробовать ещё раз")}</Text></Pressable> : null}</View> : null}
            {!busy ? <Pressable accessibilityRole="button" accessibilityLabel={mt("Спросить наставника")} onPress={ask} style={({ pressed }) => [styles.ask, { backgroundColor: colors.greenBright, opacity: pressed ? 0.75 : 1 }]}><MentorQuestionIcon name="message" size={23} color="#FFFFFF" /><Text style={styles.askText}>{mt("Спросить наставника")}</Text></Pressable> : null}
        </ScrollView>
    </>
}

const styles = StyleSheet.create({
    body: { width: "100%", maxWidth: 560, alignSelf: "center", padding: 22, gap: 15, paddingBottom: 30 },
    title: { fontSize: 30, lineHeight: 35, fontWeight: "800", letterSpacing: -0.8 }, heading: { fontSize: 23, fontWeight: "800", marginTop: 6 },
    caption: { fontSize: 14, lineHeight: 21, fontWeight: "500" }, copy: { fontSize: 16, lineHeight: 24, fontWeight: "500" },
    budget: { borderRadius: 19, padding: 17, gap: 5 }, budgetValue: { fontSize: 19, fontWeight: "800" },
    card: { borderRadius: 25, overflow: "hidden", marginTop: 3 }, photo: { height: 176, width: "100%", alignItems: "center", justifyContent: "center" }, hero: { height: 220, borderRadius: 24, overflow: "hidden" },
    cardText: { padding: 18, gap: 7 }, dishName: { fontSize: 22, lineHeight: 27, fontWeight: "800", letterSpacing: -0.4 }, calories: { fontSize: 19, fontWeight: "800" },
    recipeLink: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: 7 }, linkText: { fontWeight: "700", fontSize: 16 },
    macros: { flexDirection: "row", borderRadius: 19, paddingVertical: 18 }, macro: { flex: 1, alignItems: "center", gap: 5 }, macroValue: { fontSize: 20, fontWeight: "800" }, macroLabel: { fontSize: 11, fontWeight: "600" },
    ingredient: { flexDirection: "row", gap: 12, alignItems: "center", paddingBottom: 10, borderBottomWidth: StyleSheet.hairlineWidth }, dot: { width: 5, height: 5, borderRadius: 3 },
    step: { flexDirection: "row", gap: 12, alignItems: "flex-start", marginBottom: 5 }, stepNumber: { width: 30, height: 30, borderRadius: 11, alignItems: "center", justifyContent: "center" }, stepText: { fontSize: 15, fontWeight: "800" },
    credit: { fontSize: 11, lineHeight: 17, fontWeight: "500" }, ask: { minHeight: 54, borderRadius: 18, flexDirection: "row", gap: 10, alignItems: "center", justifyContent: "center", padding: 14, marginTop: 8 }, askText: { color: "#FFFFFF", fontSize: 17, fontWeight: "700" },
    skeleton: { height: 230, borderRadius: 25 }, error: { gap: 12, paddingVertical: 10 },
})
