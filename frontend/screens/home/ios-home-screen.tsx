import { Image, Pressable, ScrollView, Text, View } from "react-native"
import { useRouter } from "expo-router"

import { ROUTES } from "@/constants/routes"
import { useAppSafeAreaInsets } from "@/hooks/use-app-safe-area-insets"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import type { Language } from "@/i18n/translations"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { createIosHomeScreenStyles } from "@/screens/home/ios-home-screen.styles"

const COPY = {
    ru: {
        eyebrow: "Elixir Peptide",
        title: "Личный кабинет и поддержка",
        body: "Управляйте профилем, следите за статусом существующих заказов и обращайтесь в службу поддержки.",
        section: "Что доступно",
        support: "Поддержка",
        supportBody: "Напишите команде и следите за ответами.",
        history: "История заказов",
        historyBody: "Проверяйте текущие и завершённые заказы.",
        profile: "Личные данные",
        profileBody: "Обновляйте контактную информацию и настройки.",
        company: "О компании",
        companyBody: "Контакты и официальные реквизиты.",
        signIn: "Войти в аккаунт",
        signInBody: "Авторизуйтесь для поддержки и истории заказов.",
        noticeLabel: "Медицинская информация",
        noticeTitle: "Решения о здоровье принимайте вместе с врачом",
        noticeBody: "Приложение не предоставляет диагнозы, схемы лечения, дозировки или индивидуальные медицинские рекомендации. Перед любыми медицинскими решениями обратитесь к квалифицированному врачу.",
    },
    en: {
        eyebrow: "Elixir Peptide",
        title: "Your account and support",
        body: "Manage your profile, follow existing order statuses, and contact the support team.",
        section: "Available here",
        support: "Support",
        supportBody: "Message the team and follow their replies.",
        history: "Order history",
        historyBody: "Check active and completed orders.",
        profile: "Personal details",
        profileBody: "Update your contact information and preferences.",
        company: "Company information",
        companyBody: "Contacts and official company details.",
        signIn: "Sign in",
        signInBody: "Sign in to access support and order history.",
        noticeLabel: "Medical information",
        noticeTitle: "Make health decisions with a doctor",
        noticeBody: "The app does not provide diagnoses, treatment plans, dosages, or personalized medical recommendations. Consult a qualified doctor before making any medical decisions.",
    },
    kz: {
        eyebrow: "Elixir Peptide",
        title: "Жеке кабинет және қолдау",
        body: "Профильді басқарыңыз, бар тапсырыстардың күйін бақылаңыз және қолдау қызметіне хабарласыңыз.",
        section: "Қолжетімді бөлімдер",
        support: "Қолдау",
        supportBody: "Командаға жазыңыз және жауаптарды бақылаңыз.",
        history: "Тапсырыстар тарихы",
        historyBody: "Белсенді және аяқталған тапсырыстарды тексеріңіз.",
        profile: "Жеке деректер",
        profileBody: "Байланыс ақпараты мен баптауларды жаңартыңыз.",
        company: "Компания туралы",
        companyBody: "Байланыстар және ресми деректемелер.",
        signIn: "Аккаунтқа кіру",
        signInBody: "Қолдау мен тапсырыстар тарихы үшін кіріңіз.",
        noticeLabel: "Медициналық ақпарат",
        noticeTitle: "Денсаулық туралы шешімді дәрігермен бірге қабылдаңыз",
        noticeBody: "Қолданба диагноз, емдеу жоспары, дозалау немесе жеке медициналық кеңес бермейді. Медициналық шешім қабылдамас бұрын білікті дәрігерге жүгініңіз.",
    },
} as const

const LANGUAGES: { code: Language; label: string }[] = [
    { code: "ru", label: "RU" },
    { code: "en", label: "EN" },
    { code: "kz", label: "KZ" },
]

export default function IosHomeScreen() {
    const styles = useThemeStyles(createIosHomeScreenStyles)
    const { top } = useAppSafeAreaInsets()
    const { isAuthenticated } = useAuth()
    const { language, setLanguage } = useLanguage()
    const router = useRouter()
    const copy = COPY[language]
    const accountRoute = isAuthenticated ? ROUTES.profile : ROUTES.login
    const actions = isAuthenticated
        ? [
              { body: copy.supportBody, icon: "💬", route: `${ROUTES.chat}?mode=support`, title: copy.support },
              { body: copy.historyBody, icon: "🧾", route: ROUTES.profileHistory, title: copy.history },
              { body: copy.profileBody, icon: "👤", route: ROUTES.personalData, title: copy.profile },
              { body: copy.companyBody, icon: "ⓘ", route: ROUTES.contacts, title: copy.company },
          ]
        : [
              { body: copy.signInBody, icon: "↗", route: accountRoute, title: copy.signIn },
              { body: copy.companyBody, icon: "ⓘ", route: ROUTES.contacts, title: copy.company },
          ]

    return (
        <ScrollView
            contentContainerStyle={[styles.content, { paddingTop: Math.max(top + 34, 60) }]}
            style={styles.screen}
        >
            <View style={styles.hero}>
                <View pointerEvents="none" style={styles.heroGlow} />
                <View style={styles.heroToolbar}>
                    <Image source={require("@/assets/images/icon.png")} resizeMode="contain" style={styles.logo} />
                    <View accessibilityRole="tablist" style={styles.languageSwitcher}>
                        {LANGUAGES.map((option) => {
                            const selected = option.code === language
                            return (
                                <Pressable
                                    key={option.code}
                                    accessibilityLabel={option.label}
                                    accessibilityRole="tab"
                                    accessibilityState={{ selected }}
                                    onPress={() => setLanguage(option.code)}
                                    style={[styles.languageOption, selected && styles.languageOptionSelected]}
                                >
                                    <Text style={[styles.languageOptionText, selected && styles.languageOptionTextSelected]}>
                                        {option.label}
                                    </Text>
                                </Pressable>
                            )
                        })}
                    </View>
                </View>
                <Text style={styles.eyebrow}>{copy.eyebrow}</Text>
                <Text style={styles.title}>{copy.title}</Text>
                <Text style={styles.body}>{copy.body}</Text>
            </View>

            <Text style={styles.sectionTitle}>{copy.section}</Text>
            <View style={styles.actionGrid}>
                {actions.map((action) => (
                    <Pressable
                        key={action.title}
                        accessibilityLabel={action.title}
                        accessibilityRole="button"
                        onPress={() => router.push(action.route as never)}
                        style={({ pressed }) => [styles.actionCard, pressed && styles.actionCardPressed]}
                    >
                        <Text style={styles.actionIcon}>{action.icon}</Text>
                        <Text style={styles.actionTitle}>{action.title}</Text>
                        <Text style={styles.actionBody}>{action.body}</Text>
                    </Pressable>
                ))}
            </View>

            <View style={styles.notice}>
                <Text style={styles.noticeLabel}>{copy.noticeLabel}</Text>
                <Text style={styles.noticeTitle}>{copy.noticeTitle}</Text>
                <Text style={styles.noticeBody}>{copy.noticeBody}</Text>
            </View>
        </ScrollView>
    )
}
