import { Pressable, Text, View } from "react-native"

import type { HeaderMenuProps } from "@/components/header/header-menu.types"

export function HeaderMenu({
    isOpen,
    onClose,
    onSignOut,
    onToggle,
    styles,
    t,
}: HeaderMenuProps) {
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
                    <Pressable
                        accessibilityLabel={t("nav.signOut")}
                        accessibilityRole="button"
                        onPress={() => {
                            onClose()
                            void onSignOut()
                        }}
                        style={({ pressed }) => [styles.menuAction, pressed && styles.menuActionPressed]}
                    >
                        <Text style={styles.signOutText}>{t("common.signOut")}</Text>
                    </Pressable>
                </View>
            ) : null}
        </>
    )
}
