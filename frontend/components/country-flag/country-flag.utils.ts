import type { DimensionValue } from "react-native"

export function isDimensionValue(value: unknown): value is DimensionValue {
    return typeof value === "number" || typeof value === "string"
}
