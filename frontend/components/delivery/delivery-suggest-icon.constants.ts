import type { DeliveryGeoSuggestResult } from "@/services/api/delivery.types"

type DeliverySuggestIconLayer = {
    d: string
    fill?: string
    stroke?: string
    strokeWidth?: number
    strokeLinecap?: "butt" | "round" | "square"
    strokeLinejoin?: "bevel" | "miter" | "round"
}

export type DeliverySuggestIconName =
    | "airport"
    | "bank"
    | "business"
    | "country"
    | "district"
    | "drugstore"
    | "food"
    | "gasStation"
    | "hotel"
    | "house"
    | "locality"
    | "metro"
    | "place"
    | "province"
    | "railway"
    | "store"
    | "street"
    | "vegetation"

export type DeliverySuggestIconDefinition = {
    backgroundColor: string
    layers: DeliverySuggestIconLayer[]
    viewBox: string
}

const PALETTE = {
    amber: "#F4C542",
    amberSoft: "#FEF3C7",
    blue: "#2563EB",
    blueSoft: "#DBEAFE",
    brown: "#8B5E3C",
    emerald: "#0F9F6E",
    emeraldSoft: "#DCFCE7",
    indigo: "#4F46E5",
    indigoSoft: "#EDE9FE",
    red: "#DC2626",
    redSoft: "#FEE2E2",
    rose: "#BE185D",
    roseSoft: "#FCE7F3",
    sky: "#0284C7",
    skySoft: "#E0F2FE",
    slate: "#334155",
    slateSoft: "#F1F5F9",
    teal: "#0F766E",
    tealSoft: "#DCFDFC",
    violet: "#7E22CE",
    violetSoft: "#F3E8FF",
    warm: "#F97316",
    warmSoft: "#FFF7ED",
    yellowSoft: "#FFF7CC",
} as const

export const DELIVERY_SUGGEST_ICON_BADGE_SIZE = 34
export const DELIVERY_SUGGEST_ICON_SIZE = 24

export const DELIVERY_SUGGEST_ICON_DEFINITIONS: Record<
    DeliverySuggestIconName,
    DeliverySuggestIconDefinition
> = {
    airport: {
        backgroundColor: PALETTE.blueSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M21.624 1.6a3.371 3.371 0 0 0-4.307.439l-2.339 2.34c-.148.147-.294.3-.439.445l-4.9-3.576A1.009 1.009 0 0 0 8.757 1.1L4.125 2.507a1 1 0 0 0-.416 1.664L9.64 10.1c-.859.981-1.631 1.891-2.346 2.764l-.056.07H3.611a1 1 0 0 0-.707.293L1.293 14.84A1 1 0 0 0 1.486 16.4L5.3 18.691l2.288 3.814a1 1 0 0 0 1.564.192l1.611-1.61a1 1 0 0 0 .293-.707V16.753l.07-.057c.87-.713 1.78-1.484 2.765-2.345l5.93 5.93a1 1 0 0 0 1.664-.416l1.41-4.632a1 1 0 0 0-.15-.88l-3.576-4.9c.149-.145.3-.291.445-.438L22.04 6.587A3.28 3.28 0 0 0 21.624 1.6Z",
                fill: PALETTE.blue,
            },
        ],
    },
    bank: {
        backgroundColor: PALETTE.emeraldSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M2 8v4.001h1V18H2v3h16l3 .001V21h1v-3h-1v-5.999h1V8L12 2 2 8Zm4 10v-5.999h2V18H6Zm5 0v-5.999h2V18h-2Zm7 0h-2v-5.999h2V18ZM14 8a2 2 0 1 1-4.001-.001A2 2 0 0 1 14 8Z",
                fill: PALETTE.emerald,
            },
        ],
    },
    business: {
        backgroundColor: PALETTE.skySoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M4 20h16v-2h-2V8h-4V4H4v14H2v2h2Zm8-2V10h2v8h-2Zm4 0V10h2v8h-2ZM6 7h2v2H6V7Zm0 4h2v2H6v-2Zm0 4h2v2H6v-2Zm4-8h2v2h-2V7Z",
                fill: PALETTE.teal,
            },
        ],
    },
    country: {
        backgroundColor: PALETTE.blueSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z",
                stroke: PALETTE.blue,
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeWidth: 1.8,
            },
            {
                d: "M12 3c2.5 2.4 4 5.6 4 9s-1.5 6.6-4 9c-2.5-2.4-4-5.6-4-9s1.5-6.6 4-9Z",
                stroke: PALETTE.blue,
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeWidth: 1.6,
            },
            {
                d: "M4.5 9h15M4.5 15h15",
                stroke: PALETTE.blue,
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeWidth: 1.6,
            },
        ],
    },
    district: {
        backgroundColor: PALETTE.violetSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h6v6h-6v-6Z",
                fill: PALETTE.violet,
            },
        ],
    },
    drugstore: {
        backgroundColor: PALETTE.redSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z",
                fill: "#FFFFFF",
                stroke: PALETTE.red,
                strokeLinejoin: "round",
                strokeWidth: 1.8,
            },
            {
                d: "M11 7h2v3h3v2h-3v3h-2v-3H8v-2h3V7Z",
                fill: PALETTE.red,
            },
        ],
    },
    food: {
        backgroundColor: PALETTE.yellowSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M8.7 8.4c0-.7.4-1.1.8-1.5.4-.4.7-.7.7-1.4M13.8 8.4c0-.7.4-1.1.8-1.5.4-.4.7-.7.7-1.4",
                stroke: PALETTE.amber,
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeWidth: 1.7,
            },
            {
                d: "M6.8 11.1c1.4-.8 3.1-1.3 5.2-1.3 2 0 3.7.5 5.2 1.3v1.5H6.8v-1.5Z",
                fill: PALETTE.amber,
            },
            {
                d: "M5.4 13.8c.4 3.2 2.8 5.2 6.6 5.2 3.8 0 6.2-2 6.6-5.2H5.4Z",
                fill: PALETTE.brown,
            },
        ],
    },
    gasStation: {
        backgroundColor: PALETTE.redSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M7 17H12",
                stroke: PALETTE.red,
                strokeLinecap: "round",
                strokeWidth: 1.6,
            },
            {
                d: "M17 22H2",
                stroke: PALETTE.red,
                strokeLinecap: "round",
                strokeWidth: 1.6,
            },
            {
                d: "M19.5 4L20.7331 4.98647C20.8709 5.09673 20.9398 5.15186 21.0025 5.20805C21.5937 5.73807 21.9508 6.48086 21.9953 7.27364C22 7.35769 22 7.44594 22 7.62244V18.5C22 19.3284 21.3284 20 20.5 20C19.6716 20 19 19.3284 19 18.5V18.4286C19 17.6396 18.3604 17 17.5714 17H16",
                stroke: PALETTE.red,
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeWidth: 1.5,
            },
            {
                d: "M22 8H20.5C19.6716 8 19 8.67157 19 9.5V11.9189C19 12.5645 19.4131 13.1377 20.0257 13.3419L22 14",
                stroke: PALETTE.red,
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeWidth: 1.5,
            },
            {
                d: "M11 6H8C7.05719 6 6.58579 6 6.29289 6.29289C6 6.58579 6 7.05719 6 8C6 8.94281 6 9.41421 6.29289 9.70711C6.58579 10 7.05719 10 8 10H11C11.9428 10 12.4142 10 12.7071 9.70711C13 9.41421 13 8.94281 13 8C13 7.05719 13 6.58579 12.7071 6.29289C12.4142 6 11.9428 6 11 6Z",
                stroke: PALETTE.red,
                strokeWidth: 1.5,
            },
            {
                d: "M16 22V15M3 22V18M3 14V8C3 5.17157 3 3.75736 3.87868 2.87868C4.75736 2 6.17157 2 9 2H10C12.8284 2 14.2426 2 15.1213 2.87868C16 3.75736 16 5.17157 16 8V11",
                stroke: PALETTE.red,
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeWidth: 1.5,
            },
        ],
    },
    hotel: {
        backgroundColor: PALETTE.amberSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M4 19V9h2v4h12a2 2 0 0 1 2 2v4h-2v-2H6v2H4Zm4-6.5A1.5 1.5 0 1 0 8 9.5a1.5 1.5 0 0 0 0 3Zm4.5-2.5H15a2 2 0 0 1 2 2v1h-4.5V10Z",
                fill: PALETTE.brown,
            },
        ],
    },
    house: {
        backgroundColor: PALETTE.amberSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5.2v-5.6H9.2V21H4a1 1 0 0 1-1-1v-9.5Z",
                fill: PALETTE.brown,
            },
        ],
    },
    locality: {
        backgroundColor: PALETTE.skySoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M3 20h18v-2h-1V9h-5v9h-2V5H7v13H3v2Zm6-9h2v2H9v-2Zm0 4h2v2H9v-2Zm8-2h1v5h-1v-5Z",
                fill: PALETTE.sky,
            },
        ],
    },
    metro: {
        backgroundColor: PALETTE.roseSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M6 19V5h2.3L12 11l3.7-6H18v14h-2V9.2l-3 4.6h-2L8 9.2V19H6Z",
                fill: PALETTE.rose,
            },
        ],
    },
    place: {
        backgroundColor: PALETTE.blueSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M12 21s6-5.3 6-10.2A6 6 0 1 0 6 10.8C6 15.7 12 21 12 21Zm0-8.5A2.5 2.5 0 1 1 12 7a2.5 2.5 0 0 1 0 5.5Z",
                fill: PALETTE.blue,
            },
        ],
    },
    province: {
        backgroundColor: PALETTE.indigoSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M4 6.5 9 4l6 2.5L20 4v13.5L15 20l-6-2.5L4 20V6.5Z",
                stroke: PALETTE.indigo,
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeWidth: 1.7,
            },
            {
                d: "M9 4v13.5M15 6.5V20",
                stroke: PALETTE.indigo,
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeWidth: 1.5,
            },
        ],
    },
    railway: {
        backgroundColor: PALETTE.slateSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M6 4h12M5 10h14M4 16h16M9.0002 3.00005 4.00009 21M20 21 15 3",
                stroke: PALETTE.slate,
                strokeLinecap: "round",
                strokeLinejoin: "round",
                strokeWidth: 1.8,
            },
        ],
    },
    store: {
        backgroundColor: PALETTE.warmSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M7 8V7a5 5 0 0 1 10 0v1h2a1 1 0 0 1 1 1v8.2A3.8 3.8 0 0 1 16.2 21H7.8A3.8 3.8 0 0 1 4 17.2V9a1 1 0 0 1 1-1h2Zm2 0h6V7a3 3 0 1 0-6 0v1Zm-2 2v7.2A1.8 1.8 0 0 0 7.8 19h8.4a1.8 1.8 0 0 0 1.8-1.8V10h-1v2a1 1 0 1 1-2 0v-2H9v2a1 1 0 1 1-2 0v-2H7Z",
                fill: PALETTE.warm,
            },
        ],
    },
    street: {
        backgroundColor: PALETTE.slateSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M11 3h2v18h-2V3Zm2 3h7l-2.4 2.4L20 10.8h-7V6Zm-2 6H4l2.4 2.4L4 16.8h7V12Z",
                fill: PALETTE.slate,
            },
        ],
    },
    vegetation: {
        backgroundColor: PALETTE.emeraldSoft,
        viewBox: "0 0 24 24",
        layers: [
            {
                d: "M12 3c-2.6 0-4.7 2-4.7 4.5 0 .4 0 .8.1 1.1A4.5 4.5 0 0 0 4 13c0 2.8 2.2 5 5 5h2v3h2v-3h2c2.8 0 5-2.2 5-5 0-2.1-1.4-4-3.4-4.5.1-.3.1-.7.1-1.1C16.7 5 14.6 3 12 3Z",
                fill: PALETTE.emerald,
            },
        ],
    },
}

const TAG_ICON_OVERRIDES: Record<string, DeliverySuggestIconName> = {
    airport: "airport",
    bank: "bank",
    banks: "bank",
    business: "business",
    cafe: "food",
    country: "country",
    district: "district",
    drugstore: "drugstore",
    drugstores: "drugstore",
    "fast food": "food",
    fuel: "gasStation",
    "gas station": "gasStation",
    hotel: "hotel",
    house: "house",
    locality: "locality",
    metro: "metro",
    office: "business",
    pharmacy: "drugstore",
    place: "place",
    province: "province",
    railway: "railway",
    restaurant: "food",
    restaurants: "food",
    route: "street",
    shopping: "store",
    station: "railway",
    street: "street",
    supermarket: "store",
    vegetation: "vegetation",
}

const ICON_KEY_TO_ICON_NAME: Record<string, DeliverySuggestIconName> = {
    business: "business",
    country: "country",
    district: "district",
    food: "food",
    house: "house",
    locality: "locality",
    metro: "metro",
    place: "place",
    province: "province",
    store: "store",
    street: "street",
    vegetation: "vegetation",
}

function normalizeIconToken(value: string | null | undefined) {
    return value?.trim().toLowerCase() ?? ""
}

export function getDeliverySuggestIconName(
    result: Pick<DeliveryGeoSuggestResult, "icon_key" | "primary_tag" | "tags" | "type">,
): DeliverySuggestIconName {
    const normalizedTags = new Set(result.tags.map((tag) => normalizeIconToken(tag)))
    const primaryTag = normalizeIconToken(result.primary_tag)

    if (primaryTag) {
        normalizedTags.add(primaryTag)
    }

    for (const tag of normalizedTags) {
        const matchedIcon = TAG_ICON_OVERRIDES[tag]

        if (matchedIcon) {
            return matchedIcon
        }
    }

    const iconKey = normalizeIconToken(result.icon_key)

    if (iconKey && ICON_KEY_TO_ICON_NAME[iconKey]) {
        return ICON_KEY_TO_ICON_NAME[iconKey]
    }

    if (normalizeIconToken(result.type) === "business") {
        return "business"
    }

    return "place"
}
