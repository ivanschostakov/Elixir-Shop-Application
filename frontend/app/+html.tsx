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
                <style
                    dangerouslySetInnerHTML={{
                        __html: `
                            :root {
                                --elixir-color-background: #FFFFFF;
                                --elixir-color-page-background: #F3F5F8;
                                --telegram-viewport-height: 100%;
                                --telegram-viewport-stable-height: 100%;
                                background: var(--elixir-color-page-background);
                            }

                            html,
                            body,
                            #root {
                                background: var(--elixir-color-page-background);
                                min-height: var(--telegram-viewport-height);
                                overscroll-behavior: none;
                            }

                            body {
                                margin: 0;
                            }
                        `,
                    }}
                />
                <script
                    dangerouslySetInnerHTML={{
                        __html: `
                            (() => {
                                try {
                                    const theme = window.localStorage?.getItem("elixirpeptide-theme")

                                    if (theme === "dark") {
                                        document.documentElement.style.setProperty("--elixir-color-background", "#111827")
                                        document.documentElement.style.setProperty("--elixir-color-page-background", "#070A0F")
                                        document.documentElement.style.colorScheme = "dark"
                                    }
                                } catch {}
                            })();
                        `,
                    }}
                />
                <script src="https://telegram.org/js/telegram-web-app.js"></script>
            </head>
            <body>{children}</body>
        </html>
    )
}
