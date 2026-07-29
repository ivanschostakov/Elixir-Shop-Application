import type { ProductQuestionRead } from "@/types/product"
import type { Dispatch, SetStateAction } from "react"

export type UseProductQuestionsResult = {
    questions: ProductQuestionRead[]
    total: number
    loading: boolean
    error: string | null
    reload: () => Promise<{ items: ProductQuestionRead[]; total: number } | null>
    setQuestions: Dispatch<SetStateAction<{ items: ProductQuestionRead[]; total: number }>>
}
