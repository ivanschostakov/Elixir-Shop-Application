import type { ReactNode } from "react"
import { ActivityIndicator, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import type { useCompanion } from "@/screens/chat/companion"
import { MentorButton as Button, MentorIcon, MentorText as Copy, mentorStyles as styles, useMentorPalette } from "@/screens/chat/mentor-ui"

type Controller = ReturnType<typeof useCompanion>

/** Keep mentor entry visible even when its profile cannot be loaded or is disabled. */
export function MentorEntry({ controller: c, children }: { controller: Controller; children: ReactNode }) {
    const { t } = useLanguage()
    const colors = useMentorPalette()
    const ready = c.state?.available && c.state.dialogue_protocol === 2 && "mentor" in c.state
    if (ready && c.enabled) return children

    return <View testID="mentor-entry" style={[styles.body, { backgroundColor: colors.surface }]}>
        <View style={styles.header}>
            <View style={[styles.avatar, { backgroundColor: colors.mint }]}><MentorIcon name="leaf" size={26} /></View>
            <Copy heading>{mt("Наставник ElixirPeptide")}</Copy>
        </View>
        {!c.initialized && !c.error ? <ActivityIndicator accessibilityLabel={t("common.loading")} color={colors.greenBright} /> : !ready ? <>
            <Copy>{c.error || mt("Наставник временно недоступен. Попробуйте ещё раз.")}</Copy>
            <Button label={mt("Обновить данные")} onPress={() => void c.attempt(c.refresh)} />
        </> : <>
            <Copy heading>{mt("Начнём знакомство")}</Copy>
            <Copy>{mt("Питание, тренировки, вес и ваш курс — всё в одном месте.")}</Copy>
            {c.error ? <Copy>{c.error}</Copy> : null}
            <Button label={c.state?.profile ? mt("Возобновить сопровождение") : mt("Включить")} primary disabled={c.busy} onPress={() => c.setEditor({ page: "consent" })} />
        </>}
    </View>
}
