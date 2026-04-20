import React from "react";
import { View } from "react-native";
import { debugGridStyles } from "./debug-grid.styles";

export function DebugGrid() {
    const count = 12;
    const lines = Array.from({ length: count + 1 });

    return (
        <View style={[debugGridStyles.overlay, { pointerEvents: "none" }]}>
            {lines.map((_, i) => (
                <View
                    key={`v-${i}`}
                    style={[
                        debugGridStyles.vLine,
                        { left: `${(i / count) * 100}%` },
                        i === count / 2 && debugGridStyles.centerLine,
                    ]}
                />
            ))}

            {lines.map((_, i) => (
                <View
                    key={`h-${i}`}
                    style={[
                        debugGridStyles.hLine,
                        { top: `${(i / count) * 100}%` },
                        i === count / 2 && debugGridStyles.centerLine,
                    ]}
                />
            ))}
        </View>
    );
}
