import { useEffect, useState } from "react"
import { ActivityIndicator, Image, Modal, Pressable, StyleSheet, Text, View } from "react-native"
import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from "expo-audio"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { useLanguage } from "@/providers/language-provider"
import { CHAT_IDLE_AUDIO_MODE } from "@/screens/chat/chat-screen.constants"

export type CommunityMediaSource = {
    filename: string
    mimeType: string | null
    uri: string
}

export function canPreviewCommunityMedia(mimeType: string | null | undefined) {
    return mimeType?.startsWith("image/") === true || mimeType?.startsWith("audio/") === true
}

function formatPlaybackTime(seconds: number) {
    if (!Number.isFinite(seconds) || seconds < 0) return "0:00"
    const wholeSeconds = Math.floor(seconds)
    const minutes = Math.floor(wholeSeconds / 60)
    return `${minutes}:${String(wholeSeconds % 60).padStart(2, "0")}`
}

export function CommunityMediaViewer({ media, onClose }: { media: CommunityMediaSource; onClose: () => void }) {
    const { t } = useLanguage()
    const { top, bottom } = useSafeAreaInsets()
    const [imageFailed, setImageFailed] = useState(false)
    const isAudio = media.mimeType?.startsWith("audio/") === true
    const audioPlayer = useAudioPlayer(isAudio ? media.uri : null, { updateInterval: 200 })
    const audioStatus = useAudioPlayerStatus(audioPlayer)
    const duration = Math.max(audioStatus.duration || 0, 0)
    const progress = duration > 0 ? Math.min(Math.max(audioStatus.currentTime / duration, 0), 1) : 0

    useEffect(() => {
        if (!isAudio) return
        void setAudioModeAsync(CHAT_IDLE_AUDIO_MODE)
        return () => audioPlayer.pause()
    }, [audioPlayer, isAudio])

    const close = () => {
        audioPlayer.pause()
        onClose()
    }

    const toggleAudio = () => {
        if (audioStatus.playing) {
            audioPlayer.pause()
            return
        }
        if (duration > 0 && audioStatus.currentTime >= duration - 0.1) {
            void audioPlayer.seekTo(0).then(() => audioPlayer.play())
            return
        }
        audioPlayer.play()
    }

    const seekBy = (seconds: number) => {
        const nextTime = Math.min(Math.max(audioStatus.currentTime + seconds, 0), duration || Number.MAX_SAFE_INTEGER)
        void audioPlayer.seekTo(nextTime)
    }

    return (
        <Modal animationType="fade" onRequestClose={close} statusBarTranslucent transparent visible>
            <View style={styles.backdrop}>
                <View style={[styles.header, { paddingTop: Math.max(top, 12) }]}>
                    <Text numberOfLines={1} style={styles.filename}>{media.filename}</Text>
                    <Pressable accessibilityLabel={t("chat.mediaClose")} onPress={close} style={styles.closeButton}>
                        <Text style={styles.closeText}>×</Text>
                    </Pressable>
                </View>

                <View style={styles.mediaStage}>
                    {isAudio ? (
                        <View style={styles.audioCard}>
                            <View style={styles.audioArtwork}><Text style={styles.audioArtworkText}>♫</Text></View>
                            <Text numberOfLines={2} style={styles.audioTitle}>{media.filename}</Text>
                            <View style={styles.progressTrack}>
                                <View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
                            </View>
                            <View style={styles.timeRow}>
                                <Text style={styles.timeText}>{formatPlaybackTime(audioStatus.currentTime)}</Text>
                                <Text style={styles.timeText}>{formatPlaybackTime(duration)}</Text>
                            </View>
                            <View style={styles.audioControls}>
                                <Pressable accessibilityLabel={t("chat.mediaBackTen")} disabled={!audioStatus.isLoaded} onPress={() => seekBy(-10)} style={styles.skipButton}>
                                    <Text style={styles.skipText}>−10</Text>
                                </Pressable>
                                <Pressable accessibilityLabel={audioStatus.playing ? t("chat.mediaPause") : t("chat.mediaPlay")} disabled={!audioStatus.isLoaded} onPress={toggleAudio} style={[styles.playButton, !audioStatus.isLoaded ? styles.disabled : null]}>
                                    {audioStatus.isBuffering || !audioStatus.isLoaded ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.playText}>{audioStatus.playing ? "Ⅱ" : "▶"}</Text>}
                                </Pressable>
                                <Pressable accessibilityLabel={t("chat.mediaForwardTen")} disabled={!audioStatus.isLoaded} onPress={() => seekBy(10)} style={styles.skipButton}>
                                    <Text style={styles.skipText}>+10</Text>
                                </Pressable>
                            </View>
                        </View>
                    ) : imageFailed ? (
                        <View style={styles.unavailableCard}>
                            <Text style={styles.unavailableIcon}>▧</Text>
                            <Text style={styles.unavailableText}>{t("chat.mediaUnavailable")}</Text>
                        </View>
                    ) : (
                        <Image onError={() => setImageFailed(true)} resizeMode="contain" source={{ uri: media.uri }} style={styles.fullImage} />
                    )}
                </View>
                <View style={{ height: Math.max(bottom, 12) }} />
            </View>
        </Modal>
    )
}

const styles = StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: "rgba(3, 8, 14, 0.98)" },
    header: { minHeight: 68, paddingHorizontal: 14, paddingBottom: 10, flexDirection: "row", alignItems: "flex-end", gap: 12 },
    filename: { flex: 1, color: "#FFFFFF", fontSize: 15, lineHeight: 20, fontWeight: "700" },
    closeButton: { width: 42, height: 42, borderRadius: 21, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,255,255,0.14)" },
    closeText: { color: "#FFFFFF", fontSize: 28, lineHeight: 30, fontWeight: "400" },
    mediaStage: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 16, paddingVertical: 12 },
    fullImage: { width: "100%", height: "100%" },
    unavailableCard: { alignItems: "center", gap: 12 },
    unavailableIcon: { color: "#88BFF2", fontSize: 48 },
    unavailableText: { color: "#D7E6F4", fontSize: 15, lineHeight: 21, textAlign: "center" },
    audioCard: { width: "100%", maxWidth: 420, borderRadius: 28, padding: 24, alignItems: "center", backgroundColor: "#121D2A", borderWidth: 1, borderColor: "rgba(255,255,255,0.12)" },
    audioArtwork: { width: 112, height: 112, borderRadius: 56, alignItems: "center", justifyContent: "center", backgroundColor: "#0A84FF" },
    audioArtworkText: { color: "#FFFFFF", fontSize: 50, lineHeight: 58 },
    audioTitle: { marginTop: 20, color: "#FFFFFF", fontSize: 17, lineHeight: 23, fontWeight: "800", textAlign: "center" },
    progressTrack: { marginTop: 24, width: "100%", height: 5, borderRadius: 3, overflow: "hidden", backgroundColor: "rgba(255,255,255,0.18)" },
    progressFill: { height: "100%", borderRadius: 3, backgroundColor: "#0A84FF" },
    timeRow: { width: "100%", marginTop: 7, flexDirection: "row", justifyContent: "space-between" },
    timeText: { color: "#9EB1C4", fontSize: 11, lineHeight: 14, fontVariant: ["tabular-nums"] },
    audioControls: { marginTop: 20, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 22 },
    skipButton: { width: 52, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,255,255,0.1)" },
    skipText: { color: "#DCEAF7", fontSize: 14, fontWeight: "800" },
    playButton: { width: 66, height: 66, borderRadius: 33, alignItems: "center", justifyContent: "center", backgroundColor: "#0A84FF" },
    playText: { color: "#FFFFFF", fontSize: 25, lineHeight: 30, fontWeight: "800" },
    disabled: { opacity: 0.5 },
})
