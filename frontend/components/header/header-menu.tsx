import { useEffect, useRef } from "react"
import { Animated, Pressable, Text, View } from "react-native"
import { Path, Svg } from "react-native-svg"

import type { HeaderMenuProps } from "@/components/header/header-menu.types"
import { colors } from "@/theme/colors"

const SUN_ICON_PATH =
    "M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10ZM12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"
const MOON_ICON_PATH = "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z"
const THEME_TOGGLE_THUMB_TRANSLATE_X = 40

export function HeaderMenu({
    isOpen,
    isAuthenticated,
    language,
    onClose,
    onOpenContacts,
    onOpenPublicOffer,
    onOpenRequisites,
    onSignIn,
    onSignOut,
    onToggleLanguage,
    onToggleTheme,
    onToggle,
    styles,
    t,
    themeName,
}: HeaderMenuProps) {
    const canToggleTheme = Boolean(onToggleTheme && themeName)
    const canToggleLanguage = Boolean(onToggleLanguage && language)
    const isDarkTheme = themeName === "dark"
    const isEnglish = language === "en"
    const themeToggleProgress = useRef(new Animated.Value(isDarkTheme ? 1 : 0)).current
    const languageToggleProgress = useRef(new Animated.Value(isEnglish ? 1 : 0)).current
    const thumbTranslateX = themeToggleProgress.interpolate({
        inputRange: [0, 1],
        outputRange: [0, THEME_TOGGLE_THUMB_TRANSLATE_X],
    })
    const languageThumbTranslateX = languageToggleProgress.interpolate({
        inputRange: [0, 1],
        outputRange: [0, THEME_TOGGLE_THUMB_TRANSLATE_X],
    })

    useEffect(() => {
        Animated.timing(themeToggleProgress, {
            duration: 180,
            toValue: isDarkTheme ? 1 : 0,
            useNativeDriver: true,
        }).start()
    }, [isDarkTheme, themeToggleProgress])

    useEffect(() => {
        Animated.timing(languageToggleProgress, {
            duration: 180,
            toValue: isEnglish ? 1 : 0,
            useNativeDriver: true,
        }).start()
    }, [isEnglish, languageToggleProgress])

    return (
        <>
            <Pressable
                accessibilityLabel={t("nav.menu")}
                accessibilityRole="button"
                onPress={onToggle}
                style={({ pressed }) => [styles.menuButton, pressed && styles.menuButtonPressed]}
                hitSlop={12}
            >
                <View style={styles.menuIcon}>
                    <View style={styles.menuLine} />
                    <View style={styles.menuLine} />
                    <View style={styles.menuLine} />
                </View>
            </Pressable>

            {isOpen ? (
                <View style={styles.menuPopup}>
                    {canToggleTheme ? (
                        <>
                            <Pressable
                                accessibilityLabel={t("nav.toggleTheme")}
                                accessibilityRole="button"
                                accessibilityState={{ checked: isDarkTheme }}
                                onPress={() => {
                                    onToggleTheme?.()
                                }}
                                style={({ pressed }) => [
                                    styles.themeToggleAction,
                                    pressed && styles.menuActionPressed,
                                ]}
                            >
                                <View style={styles.themeToggleTrack}>
                                    <View pointerEvents="none" style={styles.themeToggleTrackFill} />
                                    <Animated.View
                                        style={[
                                            styles.themeToggleThumb,
                                            { transform: [{ translateX: thumbTranslateX }] },
                                        ]}
                                    />
                                    <View pointerEvents="none" style={styles.themeToggleIcons}>
                                        <View style={styles.themeToggleIconSlot}>
                                            <Svg width={17} height={17} viewBox="0 0 24 24" fill="none">
                                                <Path
                                                    d={SUN_ICON_PATH}
                                                    stroke={isDarkTheme ? colors.mutedText : colors.primary}
                                                    strokeLinecap="round"
                                                    strokeLinejoin="round"
                                                    strokeWidth={2}
                                                />
                                            </Svg>
                                        </View>
                                        <View style={styles.themeToggleIconSlot}>
                                            <Svg width={17} height={17} viewBox="0 0 24 24" fill="none">
                                                <Path
                                                    d={MOON_ICON_PATH}
                                                    stroke={isDarkTheme ? colors.primary : colors.mutedText}
                                                    strokeLinecap="round"
                                                    strokeLinejoin="round"
                                                    strokeWidth={2}
                                                />
                                            </Svg>
                                        </View>
                                    </View>
                                </View>
                            </Pressable>

                            <View style={styles.menuDivider} />
                        </>
                    ) : null}

                    {canToggleLanguage ? (
                        <>
                            <Pressable
                                accessibilityLabel={t("nav.toggleLanguage")}
                                accessibilityRole="button"
                                accessibilityState={{ checked: isEnglish }}
                                onPress={() => {
                                    onToggleLanguage?.()
                                }}
                                style={({ pressed }) => [
                                    styles.themeToggleAction,
                                    pressed && styles.menuActionPressed,
                                ]}
                            >
                                <View style={styles.themeToggleTrack}>
                                    <View pointerEvents="none" style={styles.themeToggleTrackFill} />
                                    <Animated.View
                                        style={[
                                            styles.themeToggleThumb,
                                            { transform: [{ translateX: languageThumbTranslateX }] },
                                        ]}
                                    />
                                    <View pointerEvents="none" style={styles.themeToggleIcons}>
                                        <View style={styles.themeToggleIconSlot}>
                                            <Text style={styles.languageToggleFlag}>🇷🇺</Text>
                                        </View>
                                        <View style={styles.themeToggleIconSlot}>
                                            <Text style={styles.languageToggleFlag}>🇬🇧</Text>
                                        </View>
                                    </View>
                                </View>
                            </Pressable>

                            <View style={styles.menuDivider} />
                        </>
                    ) : null}

                    <Pressable
                        accessibilityLabel={t("nav.contacts")}
                        accessibilityRole="button"
                        onPress={() => {
                            onClose()
                            onOpenContacts()
                        }}
                        style={({ pressed }) => [styles.menuAction, pressed && styles.menuActionPressed]}
                    >
                        <Text style={styles.menuActionText}>{t("nav.contacts")}</Text>
                    </Pressable>

                    <Pressable
                        accessibilityLabel={t("nav.requisites")}
                        accessibilityRole="button"
                        onPress={() => {
                            onClose()
                            onOpenRequisites()
                        }}
                        style={({ pressed }) => [styles.menuAction, pressed && styles.menuActionPressed]}
                    >
                        <Text style={styles.menuActionText}>{t("nav.requisites")}</Text>
                    </Pressable>

                    <Pressable
                        accessibilityLabel={t("nav.publicOffer")}
                        accessibilityRole="button"
                        onPress={() => {
                            onClose()
                            onOpenPublicOffer()
                        }}
                        style={({ pressed }) => [styles.menuAction, pressed && styles.menuActionPressed]}
                    >
                        <Text style={styles.menuActionText}>{t("nav.publicOffer")}</Text>
                    </Pressable>

                    <View style={styles.menuDivider} />

                    <Pressable
                        accessibilityLabel={isAuthenticated ? t("nav.signOut") : t("auth.login.submit")}
                        accessibilityRole="button"
                        onPress={() => {
                            onClose()
                            if (isAuthenticated) {
                                void onSignOut()
                                return
                            }

                            onSignIn()
                        }}
                        style={({ pressed }) => [styles.menuAction, pressed && styles.menuActionPressed]}
                    >
                        <Text style={styles.signOutText}>
                            {isAuthenticated ? t("common.signOut") : t("auth.login.submit")}
                        </Text>
                    </Pressable>
                </View>
            ) : null}
        </>
    )
}
