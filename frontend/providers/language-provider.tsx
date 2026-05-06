import { useCallback, useEffect, useMemo, useState } from "react"
import * as SecureStore from "expo-secure-store"
import { Platform } from "react-native"

import { translate, type Language } from "@/i18n/translations"
import { LanguageContext, useLanguage } from "@/providers/language-provider.context"
import type { LanguageProviderProps } from "@/providers/language-provider.types"

const LANGUAGE_STORAGE_KEY = "elixirshop-language"

function isLanguage(value: string | null): value is Language {
    return value === "ru" || value === "en"
}

function getWebStorage() {
    if (typeof window === "undefined" || typeof window.localStorage === "undefined") {
        return null
    }

    return window.localStorage
}

function getDeviceLanguage(): Language {
    const locale = Intl.DateTimeFormat().resolvedOptions().locale.toLowerCase()
    return locale.startsWith("en") ? "en" : "ru"
}

async function readStoredLanguage(): Promise<Language | null> {
    if (Platform.OS === "web") {
        const storedLanguage = getWebStorage()?.getItem(LANGUAGE_STORAGE_KEY) ?? null
        return isLanguage(storedLanguage) ? storedLanguage : null
    }

    try {
        const storedLanguage = await SecureStore.getItemAsync(LANGUAGE_STORAGE_KEY)
        return isLanguage(storedLanguage) ? storedLanguage : null
    } catch {
        return null
    }
}

async function persistLanguage(language: Language) {
    if (Platform.OS === "web") {
        getWebStorage()?.setItem(LANGUAGE_STORAGE_KEY, language)
        return
    }

    try {
        await SecureStore.setItemAsync(LANGUAGE_STORAGE_KEY, language)
    } catch {
        // The visible language still changes even if local persistence fails.
    }
}

export function LanguageProvider({ children }: LanguageProviderProps) {
    const [language, setLanguageState] = useState<Language>(getDeviceLanguage)

    useEffect(() => {
        let isMounted = true

        void readStoredLanguage().then((storedLanguage) => {
            if (isMounted && storedLanguage) {
                setLanguageState(storedLanguage)
            }
        })

        return () => {
            isMounted = false
        }
    }, [])

    const setLanguage = useCallback((nextLanguage: Language) => {
        setLanguageState(nextLanguage)
        void persistLanguage(nextLanguage)
    }, [])

    const toggleLanguage = useCallback(() => {
        setLanguage(language === "en" ? "ru" : "en")
    }, [language, setLanguage])

    const t = useCallback((key: Parameters<typeof translate>[0]) => translate(key, language), [language])

    const value = useMemo(
        () => ({
            language,
            setLanguage,
            t,
            toggleLanguage,
        }),
        [language, setLanguage, t, toggleLanguage],
    )

    return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export { useLanguage }
