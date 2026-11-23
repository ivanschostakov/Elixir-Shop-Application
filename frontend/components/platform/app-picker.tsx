import { useEffect, useState, type ReactNode } from "react"
import { Modal, Pressable, Text, View, type StyleProp, type TextStyle, type ViewStyle } from "react-native"
import { Picker } from "@react-native-picker/picker"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { createContentStyles } from "@/components/content/content.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"
import { spacing } from "@/theme/spacing"

export type AppPickerOption<TValue extends number | string> = {
    key: string
    label: string
    value: TValue
}

export type AppPickerSheetFieldProps<TValue extends number | string> = {
    disabled?: boolean
    label: string
    onChange: (value: TValue) => void
    options: readonly AppPickerOption<TValue>[]
    selectedValue: TValue
    title: string
    valueLabel: string
    wrapStyle?: StyleProp<ViewStyle>
    labelStyle?: StyleProp<TextStyle>
    triggerStyle?: StyleProp<ViewStyle>
}

export function AppPickerSheetField<TValue extends number | string>({
    disabled = false,
    label,
    onChange,
    options,
    selectedValue,
    title,
    valueLabel,
    wrapStyle,
    labelStyle,
    triggerStyle,
}: AppPickerSheetFieldProps<TValue>) {
    const contentStyles = useThemeStyles(createContentStyles)
    const [isOpen, setIsOpen] = useState(false)
    const [draftValue, setDraftValue] = useState(selectedValue)

    useEffect(() => {
        if (!isOpen) {
            setDraftValue(selectedValue)
        }
    }, [isOpen, selectedValue])

    return (
        <>
            <View style={wrapStyle}>
                <Text style={labelStyle}>{label}</Text>

                <Pressable
                    accessibilityLabel={label}
                    accessibilityRole="button"
                    disabled={disabled}
                    onPress={() => setIsOpen(true)}
                    style={({ pressed }) => [
                        contentStyles.browseTrigger,
                        !disabled && contentStyles.browseTriggerActive,
                        triggerStyle,
                        pressed && !disabled && contentStyles.browseTriggerPressed,
                    ]}
                >
                    <Text
                        numberOfLines={1}
                        style={[
                            contentStyles.browseTriggerValue,
                            disabled && contentStyles.browseTriggerPlaceholderValue,
                        ]}
                    >
                        {valueLabel}
                    </Text>
                </Pressable>
            </View>

            <Modal animationType="fade" onRequestClose={() => setIsOpen(false)} transparent visible={isOpen}>
                <AppPickerPanel
                    title={title}
                    onCancel={() => setIsOpen(false)}
                    onConfirm={() => {
                        onChange(draftValue)
                        setIsOpen(false)
                    }}
                >
                    <Picker
                        selectedValue={draftValue}
                        onValueChange={value => setDraftValue(value as TValue)}
                        style={contentStyles.browsePicker}
                    >
                        {options.map(option => (
                            <Picker.Item key={option.key} label={option.label} value={option.value} />
                        ))}
                    </Picker>
                </AppPickerPanel>
            </Modal>
        </>
    )
}

type PanelProps = {
    title: string
    onCancel: () => void
    onConfirm?: () => void
    children: ReactNode
}

export function AppPickerPanel({ title, onCancel, onConfirm, children }: PanelProps) {
    const contentStyles = useThemeStyles(createContentStyles)
    const { t } = useLanguage()
    const { bottom } = useSafeAreaInsets()

    return (
        <View style={contentStyles.browsePickerBackdrop}>
            <Pressable
                accessibilityRole="button"
                accessibilityLabel={t("common.cancel")}
                onPress={onCancel}
                style={contentStyles.browsePickerDismissArea}
            />
            <View style={[contentStyles.browsePickerSheet, { paddingBottom: Math.max(spacing.lg, bottom + spacing.sm) }]}>
                <View style={contentStyles.browsePickerHeader}>
                    <Text style={contentStyles.browsePickerTitle}>{title}</Text>
                    <View style={contentStyles.browsePickerActions}>
                        <Pressable
                            accessibilityRole="button"
                            accessibilityLabel={t("common.cancel")}
                            onPress={onCancel}
                            style={({ pressed }) => [contentStyles.browsePickerAction, pressed && contentStyles.browsePickerActionPressed]}
                        >
                            <Text style={contentStyles.browsePickerActionText}>{t("common.cancel")}</Text>
                        </Pressable>
                        {onConfirm ? (
                            <Pressable
                                accessibilityRole="button"
                                accessibilityLabel={t("common.done")}
                                onPress={onConfirm}
                                style={({ pressed }) => [contentStyles.browsePickerPrimaryAction, pressed && contentStyles.browsePickerActionPressed]}
                            >
                                <Text style={contentStyles.browsePickerPrimaryActionText}>{t("common.done")}</Text>
                            </Pressable>
                        ) : null}
                    </View>
                </View>
                {children}
            </View>
        </View>
    )
}
