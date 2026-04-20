export function getUserGreetings(displayName?: string): string {
    const hour = new Date().getHours();
    const namePart = displayName ? `, ${displayName}` : "";

    if (hour >= 5 && hour < 12) return `🌄 Утро вечера мудреней${namePart}`;
    if (hour >= 12 && hour < 17) return `🏙️ Добрый день${namePart}`;
    if (hour >= 17 && hour < 23) return `${displayName ? `${displayName}, как Ваш вечер? 🌆` : "🌆 Как Ваш вечер?"}`;
    return `🌃 Спокойной ночи${namePart}`;
}