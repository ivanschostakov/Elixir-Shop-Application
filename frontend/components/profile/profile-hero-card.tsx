import { useState } from "react"
import { Image, Modal, Pressable, Text, View } from "react-native"

import { ProfileScreenStyles } from "@/screens/profile/profile-screen.styles"
import { useCopyableProfileValue } from "@/hooks/profile/use-copyable-profile-value"
import type { ProfileHeroCardProps } from "@/components/profile/profile-hero-card.types"
import { useLanguage } from "@/providers/language-provider"

export function ProfileHeroCard({
    avatarUri,
    initials,
    displayName,
    username,
    isActive,
    isVerified,
    isUpdatingAvatar,
    onChangePhoto,
    onRemovePhoto,
}: ProfileHeroCardProps) {
    const [isAvatarViewerOpen, setIsAvatarViewerOpen] = useState(false)
    const { t } = useLanguage()
    const { handleCopy } = useCopyableProfileValue({ t })
    const usernameValue = username ? `@${username}` : null

    return (
        <>
            <View style={ProfileScreenStyles.heroCard}>
                <View style={ProfileScreenStyles.heroGlow} />

                <View style={ProfileScreenStyles.heroTopRow}>
                    <Pressable
                        accessibilityLabel={t("profile.openPhotoActions")}
                        accessibilityRole="button"
                        onPress={() => setIsAvatarViewerOpen(true)}
                        style={({ pressed }) => [
                            ProfileScreenStyles.avatarShell,
                            pressed && ProfileScreenStyles.avatarPressed,
                        ]}
                    >
                        <View style={ProfileScreenStyles.avatarCrop}>
                            {avatarUri ? (
                                <Image
                                    source={{ uri: avatarUri }}
                                    style={ProfileScreenStyles.avatarImage}
                                    resizeMode="cover"
                                />
                            ) : (
                                <Text style={ProfileScreenStyles.avatarText}>{initials || "U"}</Text>
                            )}
                        </View>
                    </Pressable>

                    <View style={ProfileScreenStyles.heroCopy}>
                        <Text style={ProfileScreenStyles.eyebrow}>{t("profile.memberBadge")}</Text>
                        <Pressable
                            accessibilityLabel={t("profile.fullName")}
                            accessibilityRole="button"
                            onPress={() => void handleCopy(displayName)}
                            style={({ pressed }) => [
                                ProfileScreenStyles.heroInfoButton,
                                pressed && ProfileScreenStyles.heroInfoButtonPressed,
                            ]}
                        >
                            <Text style={ProfileScreenStyles.name}>{displayName}</Text>
                        </Pressable>
                        <Pressable
                            accessibilityLabel={t("profile.username")}
                            accessibilityRole={usernameValue ? "button" : undefined}
                            disabled={!usernameValue}
                            onPress={() => void handleCopy(usernameValue)}
                            style={({ pressed }) => [
                                ProfileScreenStyles.heroInfoButton,
                                pressed && usernameValue && ProfileScreenStyles.heroInfoButtonPressed,
                            ]}
                        >
                            <Text style={ProfileScreenStyles.handle}>
                                @{username ?? t("profile.noUsername")}
                            </Text>
                        </Pressable>
                    </View>
                </View>

                <Text style={ProfileScreenStyles.subtitle}>{t("profile.subtitle")}</Text>

                <View style={ProfileScreenStyles.badgeRow}>
                    <View style={ProfileScreenStyles.badge}>
                        <Text style={ProfileScreenStyles.badgeText}>
                            {isActive ? t("profile.active") : t("profile.inactive")}
                        </Text>
                    </View>

                    <View style={ProfileScreenStyles.badgeSecondary}>
                        <Text style={ProfileScreenStyles.badgeSecondaryText}>
                            {isVerified ? t("profile.verified") : t("profile.notVerified")}
                        </Text>
                    </View>
                </View>
            </View>

            <Modal
                animationType="fade"
                onRequestClose={() => setIsAvatarViewerOpen(false)}
                transparent
                visible={isAvatarViewerOpen}
            >
                <View style={ProfileScreenStyles.avatarViewerBackdrop}>
                    <Pressable
                        onPress={() => setIsAvatarViewerOpen(false)}
                        style={ProfileScreenStyles.avatarViewerDismissArea}
                    />

                    <View style={ProfileScreenStyles.avatarViewerContent}>
                        <View style={ProfileScreenStyles.avatarViewerFrame}>
                            {avatarUri ? (
                                <Image
                                    source={{ uri: avatarUri }}
                                    style={ProfileScreenStyles.avatarViewerImage}
                                    resizeMode="cover"
                                />
                            ) : (
                                <View style={ProfileScreenStyles.avatarViewerPlaceholder}>
                                    <Text style={ProfileScreenStyles.avatarViewerPlaceholderText}>
                                        {initials || "U"}
                                    </Text>
                                </View>
                            )}
                        </View>

                        <Text style={ProfileScreenStyles.avatarViewerName}>{displayName}</Text>

                        <View style={ProfileScreenStyles.avatarViewerActions}>
                            <Pressable
                                accessibilityLabel={t("profile.changePhoto")}
                                accessibilityRole="button"
                                disabled={isUpdatingAvatar}
                                onPress={async () => {
                                    await onChangePhoto()
                                    setIsAvatarViewerOpen(false)
                                }}
                                style={({ pressed }) => [
                                    ProfileScreenStyles.avatarViewerPrimaryAction,
                                    (pressed || isUpdatingAvatar) && ProfileScreenStyles.avatarViewerActionPressed,
                                ]}
                            >
                                <Text style={ProfileScreenStyles.avatarViewerPrimaryActionText}>
                                    {t("profile.changePhoto")}
                                </Text>
                            </Pressable>

                            <Pressable
                                accessibilityLabel={t("profile.removePhoto")}
                                accessibilityRole="button"
                                disabled={!avatarUri || isUpdatingAvatar}
                                onPress={async () => {
                                    setIsAvatarViewerOpen(false)
                                    await onRemovePhoto()
                                }}
                                style={({ pressed }) => [
                                    ProfileScreenStyles.avatarViewerDestructiveAction,
                                    (!avatarUri || isUpdatingAvatar) && ProfileScreenStyles.avatarViewerActionDisabled,
                                    pressed && avatarUri && !isUpdatingAvatar && ProfileScreenStyles.avatarViewerActionPressed,
                                ]}
                            >
                                <Text style={ProfileScreenStyles.avatarViewerDestructiveActionText}>
                                    {t("profile.removePhoto")}
                                </Text>
                            </Pressable>
                        </View>
                    </View>
                </View>
            </Modal>
        </>
    )
}
