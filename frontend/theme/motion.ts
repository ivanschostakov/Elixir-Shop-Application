import { Easing } from "react-native"

export const motion = {
    duration: {
        press: 90,
        enter: 180,
        standard: 240,
        route: 280,
    },
    easing: {
        enter: Easing.out(Easing.cubic),
        standard: Easing.bezier(0.2, 0, 0, 1),
        exit: Easing.in(Easing.cubic),
    },
}
