import { Circle, Path, Svg } from "react-native-svg"

import type { FooterIconProps } from "@/components/footer/sticky-footer.icons.types"

export function SearchIcon({ color }: FooterIconProps) {
    return (
        <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
            <Path
                d="M12 10.9c-.61 0-1.1.49-1.1 1.1s.49 1.1 1.1 1.1c.61 0 1.1-.49 1.1-1.1s-.49-1.1-1.1-1.1zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm2.19 12.19L6 18l3.81-8.19L18 6l-3.81 8.19z"
                fill={color}
            />
        </Svg>
    )
}

export function HomeIcon({ color }: FooterIconProps) {
    return (
        <Svg width={19} height={19} viewBox="0 0 16 16" fill="none">
            <Path
                d="M1 6V15H6V11C6 9.89543 6.89543 9 8 9C9.10457 9 10 9.89543 10 11V15H15V6L8 0L1 6Z"
                fill={color}
            />
        </Svg>
    )
}

export function DiscoverIcon({ color }: FooterIconProps) {
    return (
        <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
            <Path
                d="M11 4a7 7 0 1 0 4.47 12.39l4.07 4.08 1.42-1.42-4.08-4.07A7 7 0 0 0 11 4Zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10Z"
                fill={color}
            />
        </Svg>
    )
}

export function SavedIcon({ color }: FooterIconProps) {
    return (
        <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
            <Path
                d="M12 20.5 4.9 13.8a4.8 4.8 0 0 1 6.8-6.8L12 7.3l.3-.3a4.8 4.8 0 0 1 6.8 6.8L12 20.5Z"
                fill={color}
            />
        </Svg>
    )
}

export function SmileBubbleIcon({ color }: FooterIconProps) {
    return (
        <Svg width={26} height={26} viewBox="0 0 24 24" fill="none">
            <Path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M9.93935 12.6464L7.69211 11.8973L7.69211 11.8973L7.6921 11.8973C5.3389 11.1129 4.16229 10.7207 4.16229 9.99997C4.16229 9.27921 5.3389 8.88701 7.69212 8.10261L16.2053 5.26488C17.8611 4.71295 18.689 4.43699 19.126 4.87401C19.563 5.31102 19.287 6.13892 18.7351 7.79471L15.8974 16.3079L15.8974 16.3079L15.8974 16.3079C15.113 18.6611 14.7208 19.8377 14 19.8377C13.2793 19.8377 12.8871 18.6611 12.1026 16.3079L11.3536 14.0606L15.7071 9.70708C16.0976 9.31656 16.0976 8.68339 15.7071 8.29287C15.3166 7.90234 14.6834 7.90234 14.2929 8.29287L9.93935 12.6464Z"
                fill={color}
            />
        </Svg>
    )
}

export function BasketIcon({ color }: FooterIconProps) {
    return (
        <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
            <Path
                d="M8 8L8 7C8 4.79086 9.79086 3 12 3V3C14.2091 3 16 4.79086 16 7L16 8"
                stroke={color}
                strokeWidth={2}
                strokeLinecap="round"
            />
            <Path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M3.58579 7.58579C3 8.17157 3 9.11438 3 11V14C3 17.7712 3 19.6569 4.17157 20.8284C5.34315 22 7.22876 22 11 22H13C16.7712 22 18.6569 22 19.8284 20.8284C21 19.6569 21 17.7712 21 14V11C21 9.11438 21 8.17157 20.4142 7.58579C19.8284 7 18.8856 7 17 7H7C5.11438 7 4.17157 7 3.58579 7.58579ZM10 12C10 11.4477 9.55228 11 9 11C8.44772 11 8 11.4477 8 12V14C8 14.5523 8.44772 15 9 15C9.55228 15 10 14.5523 10 14V12ZM16 12C16 11.4477 15.5523 11 15 11C14.4477 11 14 11.4477 14 12V14C14 14.5523 14.4477 15 15 15C15.5523 15 16 14.5523 16 14V12Z"
                fill={color}
            />
        </Svg>
    )
}

export function ProfileIcon({ color }: FooterIconProps) {
    return (
        <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
            <Circle cx="12" cy="8" r="3.5" stroke={color} strokeWidth="2" />
            <Path
                d="M5 19c1.7-3.2 4.1-4.8 7-4.8S17.3 15.8 19 19"
                stroke={color}
                strokeLinecap="round"
                strokeWidth="2"
            />
        </Svg>
    )
}
