import { useEffect, useMemo, useState } from "react"
import { Platform } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import {
    getTelegramViewportSnapshot,
    subscribeTelegramViewportChanges,
    type TelegramViewportSnapshot,
} from "@/services/telegram/telegram-web-app"

type AppSafeAreaInsets = {
    bottom: number
    left: number
    right: number
    top: number
}

function maxInset(...values: number[]) {
    return Math.max(0, ...values.filter((value) => Number.isFinite(value)))
}

export function useAppSafeAreaInsets(): AppSafeAreaInsets {
    const nativeInsets = useSafeAreaInsets()
    const [telegramSnapshot, setTelegramSnapshot] =
        useState<TelegramViewportSnapshot>(() => getTelegramViewportSnapshot())

    useEffect(() => {
        if (Platform.OS !== "web") {
            return
        }

        return subscribeTelegramViewportChanges(setTelegramSnapshot)
    }, [])

    return useMemo(
        () => ({
            bottom: maxInset(
                nativeInsets.bottom,
                telegramSnapshot.safeAreaInset.bottom,
                telegramSnapshot.contentSafeAreaInset.bottom,
            ),
            left: maxInset(
                nativeInsets.left,
                telegramSnapshot.safeAreaInset.left,
                telegramSnapshot.contentSafeAreaInset.left,
            ),
            right: maxInset(
                nativeInsets.right,
                telegramSnapshot.safeAreaInset.right,
                telegramSnapshot.contentSafeAreaInset.right,
            ),
            top: maxInset(
                nativeInsets.top,
                telegramSnapshot.safeAreaInset.top,
                telegramSnapshot.contentSafeAreaInset.top,
            ),
        }),
        [
            nativeInsets.bottom,
            nativeInsets.left,
            nativeInsets.right,
            nativeInsets.top,
            telegramSnapshot.contentSafeAreaInset.bottom,
            telegramSnapshot.contentSafeAreaInset.left,
            telegramSnapshot.contentSafeAreaInset.right,
            telegramSnapshot.contentSafeAreaInset.top,
            telegramSnapshot.safeAreaInset.bottom,
            telegramSnapshot.safeAreaInset.left,
            telegramSnapshot.safeAreaInset.right,
            telegramSnapshot.safeAreaInset.top,
        ],
    )
}
