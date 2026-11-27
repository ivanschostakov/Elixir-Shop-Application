import { Alert } from "react-native"

// Keep the slot through dismissal, including the native permission dialog.
let tail: Promise<void> = Promise.resolve()
export function queueStartupNotice(task: () => Promise<void>) {
    const result = tail.then(task)
    tail = result.catch(() => undefined)
    return tail
}

export function presentStartupNotice(title: string, body: string, labels: string[], cancelable = false): Promise<number> {
    return new Promise(resolve => Alert.alert(title, body, labels.map((text, index) => ({
        text, style: cancelable && index === 0 ? "cancel" : "default", onPress: () => resolve(index),
    })), { cancelable, onDismiss: () => resolve(-1) }))
}
