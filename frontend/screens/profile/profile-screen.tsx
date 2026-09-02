import { Pressable, Text, View } from "react-native"
import { router } from "expo-router"

import { ProfileHeroCard } from "@/components/profile/profile-hero-card"
import { FeedTemplate } from "@/components/templates/feed-template"
import { ROUTES } from "@/constants/routes"
import { useProfileAvatar } from "@/hooks/profile/use-profile-avatar"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { createProfileScreenStyles } from "@/screens/profile/profile-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { getProfileInitials } from "@/utils/profile/get-profile-initials"
import { themeAccentPalettes, type ThemeAccentName } from "@/theme/colors"
import { useCatalogAvailable } from "@/services/app-features"

export default function ProfileScreen() {
    const catalogAvailable = useCatalogAvailable()
    const ProfileScreenStyles = useThemeStyles(createProfileScreenStyles)
    const { user } = useAuth()
    const { language, setLanguage, t } = useLanguage()
    const { accentName, accentPalette, setAccentName, themeName, toggleTheme } = useTheme()
    const fullName = [user?.name, user?.surname].filter(Boolean).join(" ").trim()
    const displayName = fullName || t("profile.fallbackName")
    const initials = getProfileInitials(displayName)
    const {
        avatarUri,
        isUpdatingAvatar,
        handleChangePhoto,
        handleRemovePhoto,
    } = useProfileAvatar({
        userId: user?.id,
        t,
    })
    const accentOptions: ThemeAccentName[] = [
        "vividBlue",
        "archivedBlue",
        "teal",
        "emerald",
        "rose",
        "amber",
        "blackWhite",
    ]
    const accentLabel = language === "ru"
        ? "Акцент"
        : language === "kz"
          ? "Негізгі түс"
          : "Accent"

    return (
        <FeedTemplate
            contentContainerStyle={ProfileScreenStyles.content}
            scrollViewStyle={ProfileScreenStyles.container}
            style={ProfileScreenStyles.screen}
        >
            <ProfileHeroCard
                avatarUri={avatarUri}
                contactValue={user?.phoneNumber ?? user?.email}
                initials={initials}
                displayName={displayName}
                isActive={user?.isActive}
                isVerified={user?.isVerified}
                isUpdatingAvatar={isUpdatingAvatar}
                onChangePhoto={handleChangePhoto}
                onRemovePhoto={handleRemovePhoto}
            />

            <Pressable
                accessibilityLabel={t("profile.personalData.open")}
                accessibilityRole="button"
                onPress={() => router.push(ROUTES.personalData)}
                style={({ pressed }) => [
                    ProfileScreenStyles.historyCardButton,
                    pressed && ProfileScreenStyles.historyCardButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.sectionCard}>
                    <View style={ProfileScreenStyles.historyCardHeader}>
                        <View style={ProfileScreenStyles.historyCardCopy}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("profile.personalData.title")}</Text>
                            <Text style={ProfileScreenStyles.historyCardSubtitle}>{t("profile.personalData.subtitle")}</Text>
                        </View>

                        <Text style={ProfileScreenStyles.historyCardArrow}>
                            {">"}
                        </Text>
                    </View>
                </View>
            </Pressable>

            <View style={ProfileScreenStyles.sectionCard}>
                <Text style={ProfileScreenStyles.sectionTitle}>{t("profile.language")}</Text>
                <Text style={ProfileScreenStyles.sectionDescription}>{t("profile.languageSubtitle")}</Text>
                <View style={ProfileScreenStyles.preferencesChipRow}>
                    {[
                        { code: "ru" as const, label: "🇷🇺 RU" },
                        { code: "en" as const, label: "🇬🇧 EN" },
                        { code: "kz" as const, label: "🇰🇿 KZ" },
                    ].map((languageOption) => (
                        <Pressable
                            key={languageOption.code}
                            accessibilityRole="button"
                            accessibilityLabel={languageOption.label}
                            onPress={() => setLanguage(languageOption.code)}
                            style={({ pressed }) => [
                                ProfileScreenStyles.preferenceChip,
                                language === languageOption.code && [
                                    ProfileScreenStyles.preferenceChipActive,
                                    {
                                        borderColor: accentPalette.primary,
                                        backgroundColor: accentPalette.primaryMuted,
                                    },
                                ],
                                pressed && ProfileScreenStyles.preferenceChipPressed,
                            ]}
                        >
                            <Text
                                style={[
                                    ProfileScreenStyles.preferenceChipText,
                                    language === languageOption.code && [
                                        ProfileScreenStyles.preferenceChipTextActive,
                                        { color: accentPalette.primary },
                                    ],
                                ]}
                            >
                                {languageOption.label}
                            </Text>
                        </Pressable>
                    ))}
                </View>
                <View style={ProfileScreenStyles.themeModeRow}>
                    <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={themeName === "dark" ? t("common.themeDark") : t("common.themeLight")}
                        onPress={toggleTheme}
                        style={({ pressed }) => [
                            ProfileScreenStyles.preferenceChip,
                            ProfileScreenStyles.themeModeChip,
                            pressed && ProfileScreenStyles.preferenceChipPressed,
                        ]}
                    >
                        <Text style={ProfileScreenStyles.preferenceChipText}>
                            {themeName === "dark" ? t("common.themeDark") : t("common.themeLight")}
                        </Text>
                    </Pressable>
                </View>
                <Text style={ProfileScreenStyles.detailLabel}>{accentLabel}</Text>
                <View style={ProfileScreenStyles.colorSwatchRow}>
                    {accentOptions.map((accentOption) => (
                        <Pressable
                            key={accentOption}
                            accessibilityRole="button"
                            accessibilityLabel={accentOption}
                            onPress={() => setAccentName(accentOption)}
                            style={({ pressed }) => [
                                ProfileScreenStyles.colorSwatchShell,
                                accentName === accentOption && ProfileScreenStyles.colorSwatchShellActive,
                                pressed && ProfileScreenStyles.preferenceChipPressed,
                            ]}
                        >
                            <View
                                style={[
                                    ProfileScreenStyles.colorSwatch,
                                    { backgroundColor: themeAccentPalettes[accentOption].primary },
                                ]}
                            />
                        </Pressable>
                    ))}
                </View>
            </View>

            {catalogAvailable ? <Pressable
                accessibilityLabel={t("nav.favorites")}
                accessibilityRole="button"
                onPress={() => router.push(ROUTES.favorites)}
                style={({ pressed }) => [
                    ProfileScreenStyles.historyCardButton,
                    pressed && ProfileScreenStyles.historyCardButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.sectionCard}>
                    <View style={ProfileScreenStyles.historyCardHeader}>
                        <View style={ProfileScreenStyles.historyCardCopy}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("route.favorites")}</Text>
                            <Text style={ProfileScreenStyles.historyCardSubtitle}>{t("nav.favorites")}</Text>
                        </View>

                        <Text style={ProfileScreenStyles.historyCardArrow}>
                            {">"}
                        </Text>
                    </View>
                </View>
            </Pressable> : null}

            {catalogAvailable ? <Pressable
                accessibilityLabel={t("profile.discounts.open")}
                accessibilityRole="button"
                onPress={() => router.push(ROUTES.profileDiscounts)}
                style={({ pressed }) => [
                    ProfileScreenStyles.historyCardButton,
                    pressed && ProfileScreenStyles.historyCardButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.sectionCard}>
                    <View style={ProfileScreenStyles.historyCardHeader}>
                        <View style={ProfileScreenStyles.historyCardCopy}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("profile.discounts.title")}</Text>
                            <Text style={ProfileScreenStyles.historyCardSubtitle}>{t("profile.discounts.pageSubtitle")}</Text>
                        </View>

                        <Text style={ProfileScreenStyles.historyCardArrow}>
                            {">"}
                        </Text>
                    </View>
                </View>
            </Pressable> : null}

            <Pressable
                accessibilityLabel={t("profile.history.open")}
                accessibilityRole="button"
                onPress={() => router.push(ROUTES.profileHistory)}
                style={({ pressed }) => [
                    ProfileScreenStyles.historyCardButton,
                    pressed && ProfileScreenStyles.historyCardButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.sectionCard}>
                    <View style={ProfileScreenStyles.historyCardHeader}>
                        <View style={ProfileScreenStyles.historyCardCopy}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("profile.history.title")}</Text>
                            <Text style={ProfileScreenStyles.historyCardSubtitle}>{t("profile.history.subtitle")}</Text>
                        </View>

                        <Text style={ProfileScreenStyles.historyCardArrow}>
                            {">"}
                        </Text>
                    </View>
                </View>
            </Pressable>

            {catalogAvailable ? <Pressable
                accessibilityLabel={t("profile.drafts.open")}
                accessibilityRole="button"
                onPress={() => router.push(ROUTES.profileDrafts)}
                style={({ pressed }) => [
                    ProfileScreenStyles.historyCardButton,
                    pressed && ProfileScreenStyles.historyCardButtonPressed,
                ]}
            >
                <View style={ProfileScreenStyles.sectionCard}>
                    <View style={ProfileScreenStyles.historyCardHeader}>
                        <View style={ProfileScreenStyles.historyCardCopy}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("profile.drafts.title")}</Text>
                            <Text style={ProfileScreenStyles.historyCardSubtitle}>{t("profile.drafts.subtitle")}</Text>
                        </View>

                        <Text style={ProfileScreenStyles.historyCardArrow}>
                            {">"}
                        </Text>
                    </View>
                </View>
            </Pressable> : null}

            <View style={ProfileScreenStyles.sectionCard}>
                <Text style={ProfileScreenStyles.sectionDescription}>
                    {t("profile.legalSubtitle")}
                </Text>

                <Pressable
                    accessibilityLabel={t("profile.openContacts")}
                    accessibilityRole="button"
                    onPress={() => router.push(ROUTES.contacts)}
                    style={({ pressed }) => [
                        ProfileScreenStyles.historyCardButton,
                        pressed && ProfileScreenStyles.historyCardButtonPressed,
                    ]}
                >
                    <View style={ProfileScreenStyles.sectionCard}>
                        <View style={ProfileScreenStyles.historyCardHeader}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("nav.contacts")}</Text>
                            <Text style={ProfileScreenStyles.historyCardArrow}>{">"}</Text>
                        </View>
                    </View>
                </Pressable>

                <Pressable
                    accessibilityLabel={t("profile.openRequisites")}
                    accessibilityRole="button"
                    onPress={() => router.push(ROUTES.requisites)}
                    style={({ pressed }) => [
                        ProfileScreenStyles.historyCardButton,
                        pressed && ProfileScreenStyles.historyCardButtonPressed,
                    ]}
                >
                    <View style={ProfileScreenStyles.sectionCard}>
                        <View style={ProfileScreenStyles.historyCardHeader}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("nav.requisites")}</Text>
                            <Text style={ProfileScreenStyles.historyCardArrow}>{">"}</Text>
                        </View>
                    </View>
                </Pressable>

                <Pressable
                    accessibilityLabel={t("profile.openPublicOffer")}
                    accessibilityRole="button"
                    onPress={() => router.push(ROUTES.publicOffer)}
                    style={({ pressed }) => [
                        ProfileScreenStyles.historyCardButton,
                        pressed && ProfileScreenStyles.historyCardButtonPressed,
                    ]}
                >
                    <View style={ProfileScreenStyles.sectionCard}>
                        <View style={ProfileScreenStyles.historyCardHeader}>
                            <Text style={ProfileScreenStyles.historyCardTitle}>{t("nav.publicOffer")}</Text>
                            <Text style={ProfileScreenStyles.historyCardArrow}>{">"}</Text>
                        </View>
                    </View>
                </Pressable>
            </View>

        </FeedTemplate>
    )
}
