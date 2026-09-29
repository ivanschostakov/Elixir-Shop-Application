import type { SettlementResponse } from "@/services/api/settlement"

export function formatSettlementMoney(value: string | number | null | undefined): string {
    if (value === null || value === undefined || value === "") return "—"
    const amount = Number(value)
    if (!Number.isFinite(amount)) return "—"
    return new Intl.NumberFormat("ru-RU", {
        style: "currency", currency: "RUB", minimumFractionDigits: 2, maximumFractionDigits: 2,
    }).format(amount)
}

export function settlementProgramKey(program: SettlementResponse["loyalty_program"]) {
    switch (program) {
        case 0: return "profile.settlement.programNone" as const
        case 1: return "profile.settlement.programBonus" as const
        case 2: return "profile.settlement.programReferral" as const
        default: return "profile.settlement.programUnknown" as const
    }
}
