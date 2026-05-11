import type { ComponentType } from "react"

import Category1Icon from "@/assets/category-icons/1.svg"
import Category2Icon from "@/assets/category-icons/2.svg"
import Category3Icon from "@/assets/category-icons/3.svg"
import Category4Icon from "@/assets/category-icons/4.svg"
import Category5Icon from "@/assets/category-icons/5.svg"
import Category6Icon from "@/assets/category-icons/6.svg"
import Category7Icon from "@/assets/category-icons/7.svg"
import Category8Icon from "@/assets/category-icons/8.svg"
import Category9Icon from "@/assets/category-icons/9.svg"
import Category10Icon from "@/assets/category-icons/10.svg"
import Category11Icon from "@/assets/category-icons/11.svg"
import Category12Icon from "@/assets/category-icons/12.svg"
import Category13Icon from "@/assets/category-icons/13.svg"
import Category14Icon from "@/assets/category-icons/14.svg"
import Category15Icon from "@/assets/category-icons/15.svg"
import Category16Icon from "@/assets/category-icons/16.svg"
import Category17Icon from "@/assets/category-icons/17.svg"

type CategoryIconProps = {
    width?: number | string
    height?: number | string
    color?: string
}

const CATEGORY_ICON_BY_ID: Record<number, ComponentType<CategoryIconProps>> = {
    1: Category1Icon,
    2: Category2Icon,
    3: Category3Icon,
    4: Category4Icon,
    5: Category5Icon,
    6: Category6Icon,
    7: Category7Icon,
    8: Category8Icon,
    9: Category9Icon,
    10: Category10Icon,
    11: Category11Icon,
    12: Category12Icon,
    13: Category13Icon,
    14: Category14Icon,
    15: Category15Icon,
    16: Category16Icon,
    17: Category17Icon,
}

export function getDiscoverCategoryIcon(categoryId: number): ComponentType<CategoryIconProps> | null {
    return CATEGORY_ICON_BY_ID[categoryId] ?? null
}
