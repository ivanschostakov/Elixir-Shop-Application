import { createContext } from "react"

export const NativeRouteTransitionContext = createContext(false)

export type RouteAnimation = "slide_from_left" | "slide_from_right"

export const RouteTransitionContext = createContext<{
    animation: RouteAnimation
    setAnimation: (animation: RouteAnimation) => void
}>({ animation: "slide_from_right", setAnimation: () => undefined })
