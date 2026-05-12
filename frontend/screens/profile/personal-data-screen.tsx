import { useEffect, useMemo, useState } from "react"
import { ActivityIndicator, Alert, Keyboard, Pressable, Text, TextInput, View } from "react-native"

import { FeedTemplate } from "@/components/templates/feed-template"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { ProfileScreenStyles } from "@/screens/profile/profile-screen.styles"
import type { PersonalDataUpdatePayload } from "@/services/auth/auth.types"
import { getErrorMessage } from "@/utils/errors"

type PersonalDataForm = {
    username: string
    name: string
    surname: string
    email: string
    phoneNumber: string
    password: string
    repeatPassword: string
}

function normalizeFormText(value: string) {
    return value.trim()
}

export default function PersonalDataScreen() {
    const { t } = useLanguage()
    const { updatePersonalData, user } = useAuth()
    const [form, setForm] = useState<PersonalDataForm>({
        username: user?.username ?? "",
        name: user?.name ?? "",
        surname: user?.surname ?? "",
        email: user?.email ?? "",
        phoneNumber: user?.phoneNumber ?? "",
        password: "",
        repeatPassword: "",
    })
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [isSaving, setIsSaving] = useState(false)

    useEffect(() => {
        setForm((current) => ({
            ...current,
            username: user?.username ?? "",
            name: user?.name ?? "",
            surname: user?.surname ?? "",
            email: user?.email ?? "",
            phoneNumber: user?.phoneNumber ?? "",
            password: "",
            repeatPassword: "",
        }))
    }, [user?.email, user?.name, user?.phoneNumber, user?.surname, user?.username])

    const payload = useMemo<PersonalDataUpdatePayload | null>(() => {
        if (!user) {
            return null
        }

        const nextPayload: PersonalDataUpdatePayload = {}
        const username = normalizeFormText(form.username)
        const name = normalizeFormText(form.name)
        const surname = normalizeFormText(form.surname)
        const email = normalizeFormText(form.email).toLowerCase()
        const phoneNumber = normalizeFormText(form.phoneNumber)
        const password = form.password

        if (username && username !== user.username) {
            nextPayload.username = username
        }
        if (name && name !== user.name) {
            nextPayload.name = name
        }
        if (surname && surname !== user.surname) {
            nextPayload.surname = surname
        }
        if (email && email !== user.email.toLowerCase()) {
            nextPayload.email = email
        }
        if (phoneNumber !== (user.phoneNumber ?? "")) {
            nextPayload.phone_number = phoneNumber || null
        }
        if (password) {
            nextPayload.password = password
        }

        return Object.keys(nextPayload).length ? nextPayload : null
    }, [form, user])

    const updateField = (field: keyof PersonalDataForm) => (value: string) => {
        setForm((current) => ({ ...current, [field]: value }))
        setErrorMessage(null)
    }

    const handleSave = async () => {
        Keyboard.dismiss()

        if (!user || isSaving) {
            return
        }

        const username = normalizeFormText(form.username)
        const name = normalizeFormText(form.name)
        const surname = normalizeFormText(form.surname)
        const email = normalizeFormText(form.email)

        if (!username || !name || !surname || !email) {
            setErrorMessage(t("profile.personalData.required"))
            return
        }

        if (form.password || form.repeatPassword) {
            if (form.password.length < 8) {
                setErrorMessage(t("auth.error.passwordLength"))
                return
            }

            if (form.password !== form.repeatPassword) {
                setErrorMessage(t("auth.error.passwordMismatch"))
                return
            }
        }

        if (!payload) {
            Alert.alert(t("profile.personalData.noChangesTitle"), t("profile.personalData.noChangesMessage"))
            return
        }

        setIsSaving(true)
        setErrorMessage(null)

        try {
            await updatePersonalData(payload)
            setForm((current) => ({
                ...current,
                password: "",
                repeatPassword: "",
            }))
            Alert.alert(t("profile.personalData.savedTitle"), t("profile.personalData.savedMessage"))
        } catch (saveError) {
            setErrorMessage(getErrorMessage(saveError, t("profile.personalData.saveFailed")))
        } finally {
            setIsSaving(false)
        }
    }

    return (
        <FeedTemplate
            contentContainerStyle={ProfileScreenStyles.content}
            scrollViewStyle={ProfileScreenStyles.container}
            style={ProfileScreenStyles.screen}
        >
            <View style={ProfileScreenStyles.sectionCard}>
                <Text style={ProfileScreenStyles.sectionTitle}>{t("profile.personalData.title")}</Text>
                <Text style={ProfileScreenStyles.sectionDescription}>{t("profile.personalData.subtitle")}</Text>

                {errorMessage ? (
                    <View style={ProfileScreenStyles.errorBox}>
                        <Text style={ProfileScreenStyles.errorText}>{errorMessage}</Text>
                    </View>
                ) : null}

                <View style={ProfileScreenStyles.formGroup}>
                    <Text style={ProfileScreenStyles.formLabel}>{t("profile.personalData.loginLabel")}</Text>
                    <TextInput
                        autoCapitalize="none"
                        autoCorrect={false}
                        onChangeText={updateField("username")}
                        placeholder={t("auth.register.usernamePlaceholder")}
                        placeholderTextColor="#94A3B8"
                        style={ProfileScreenStyles.formInput}
                        value={form.username}
                    />
                </View>

                <View style={ProfileScreenStyles.formGroup}>
                    <Text style={ProfileScreenStyles.formLabel}>{t("profile.personalData.nameLabel")}</Text>
                    <TextInput
                        autoCapitalize="words"
                        onChangeText={updateField("name")}
                        placeholder={t("auth.register.namePlaceholder")}
                        placeholderTextColor="#94A3B8"
                        style={ProfileScreenStyles.formInput}
                        value={form.name}
                    />
                </View>

                <View style={ProfileScreenStyles.formGroup}>
                    <Text style={ProfileScreenStyles.formLabel}>{t("profile.personalData.surnameLabel")}</Text>
                    <TextInput
                        autoCapitalize="words"
                        onChangeText={updateField("surname")}
                        placeholder={t("auth.register.surnamePlaceholder")}
                        placeholderTextColor="#94A3B8"
                        style={ProfileScreenStyles.formInput}
                        value={form.surname}
                    />
                </View>

                <View style={ProfileScreenStyles.formGroup}>
                    <Text style={ProfileScreenStyles.formLabel}>{t("profile.personalData.emailLabel")}</Text>
                    <TextInput
                        autoCapitalize="none"
                        autoComplete="email"
                        keyboardType="email-address"
                        onChangeText={updateField("email")}
                        placeholder={t("auth.register.email")}
                        placeholderTextColor="#94A3B8"
                        style={ProfileScreenStyles.formInput}
                        textContentType="emailAddress"
                        value={form.email}
                    />
                </View>

                <View style={ProfileScreenStyles.formGroup}>
                    <Text style={ProfileScreenStyles.formLabel}>{t("profile.personalData.phoneLabel")}</Text>
                    <TextInput
                        autoComplete="tel"
                        keyboardType="phone-pad"
                        onChangeText={updateField("phoneNumber")}
                        placeholder={t("checkout.recipientPhonePlaceholder")}
                        placeholderTextColor="#94A3B8"
                        style={ProfileScreenStyles.formInput}
                        textContentType="telephoneNumber"
                        value={form.phoneNumber}
                    />
                </View>

                <View style={ProfileScreenStyles.formGroup}>
                    <Text style={ProfileScreenStyles.formLabel}>{t("profile.personalData.passwordLabel")}</Text>
                    <TextInput
                        autoCapitalize="none"
                        autoComplete="new-password"
                        onChangeText={updateField("password")}
                        placeholder={t("profile.personalData.passwordPlaceholder")}
                        placeholderTextColor="#94A3B8"
                        secureTextEntry
                        style={ProfileScreenStyles.formInput}
                        textContentType="newPassword"
                        value={form.password}
                    />
                </View>

                <View style={ProfileScreenStyles.formGroup}>
                    <Text style={ProfileScreenStyles.formLabel}>{t("profile.personalData.repeatPasswordLabel")}</Text>
                    <TextInput
                        autoCapitalize="none"
                        autoComplete="new-password"
                        onChangeText={updateField("repeatPassword")}
                        placeholder={t("profile.personalData.repeatPasswordPlaceholder")}
                        placeholderTextColor="#94A3B8"
                        secureTextEntry
                        style={ProfileScreenStyles.formInput}
                        textContentType="newPassword"
                        value={form.repeatPassword}
                    />
                </View>

                <Pressable
                    accessibilityLabel={t("profile.personalData.saveAction")}
                    accessibilityRole="button"
                    disabled={isSaving}
                    onPress={() => {
                        void handleSave()
                    }}
                    style={({ pressed }) => [
                        ProfileScreenStyles.primaryActionButton,
                        isSaving && ProfileScreenStyles.primaryActionButtonDisabled,
                        pressed && !isSaving && ProfileScreenStyles.primaryActionButtonPressed,
                    ]}
                >
                    {isSaving ? (
                        <ActivityIndicator color="#ffffff" />
                    ) : (
                        <Text style={ProfileScreenStyles.primaryActionButtonText}>
                            {t("profile.personalData.saveAction")}
                        </Text>
                    )}
                </Pressable>
            </View>
        </FeedTemplate>
    )
}
