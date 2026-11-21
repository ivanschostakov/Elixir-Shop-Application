export type ProfileHeroCardProps = {
    avatarUri: string | null
    contactValue?: string | null
    contactType?: "phone" | "email"
    displayName: string
    initials: string
    isActive?: boolean
    isUpdatingAvatar: boolean
    isVerified?: boolean
    onChangePhoto: () => Promise<void>
    onRemovePhoto: () => Promise<void>
}
