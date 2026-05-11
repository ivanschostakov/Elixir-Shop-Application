export type ContentTabBarItem = {
    key: string
    label: string
    isActive: boolean
    onPress: () => void
}

export type ContentTabBarProps = {
    tabs: ContentTabBarItem[]
    variant?: "default" | "onColor"
}
