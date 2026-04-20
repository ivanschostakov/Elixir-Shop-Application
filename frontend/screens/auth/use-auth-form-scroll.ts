import { useRef } from "react"
import type { LayoutChangeEvent, ScrollView } from "react-native"

function createFieldPositions<TField extends string>(fields: readonly TField[]) {
    return Object.fromEntries(fields.map((field) => [field, 0])) as Record<TField, number>
}

export function useAuthFormScroll<TField extends string>(fields: readonly TField[]) {
    const scrollRef = useRef<ScrollView>(null)
    const fieldPositions = useRef<Record<TField, number>>(createFieldPositions(fields))

    const handleFieldLayout =
        (field: TField) =>
        (event: LayoutChangeEvent) => {
            fieldPositions.current[field] = event.nativeEvent.layout.y
        }

    const scrollToField = (field: TField) => {
        requestAnimationFrame(() => {
            scrollRef.current?.scrollTo({
                y: Math.max(fieldPositions.current[field] - 24, 0),
                animated: true,
            })
        })
    }

    return {
        handleFieldLayout,
        scrollRef,
        scrollToField,
    }
}
