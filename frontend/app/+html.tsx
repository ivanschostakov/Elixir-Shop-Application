import { ScrollViewStyleReset } from "expo-router/html"
import type { ReactNode } from "react"

export default function Html({ children }: { children: ReactNode }) {
    return (
        <html lang="en">
            <head>
                <meta charSet="utf-8" />
                <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
                <meta
                    content="width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover"
                    name="viewport"
                />
                <ScrollViewStyleReset />
                <script src="https://telegram.org/js/telegram-web-app.js"></script>
            </head>
            <body>{children}</body>
        </html>
    )
}
