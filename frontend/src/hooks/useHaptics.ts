

/**
 * useHaptics - Lightweight haptic feedback hook for Android & Web
 * 
 * Uses the native AndroidBridge if running in the Android wrapper,
 * otherwise falls back to the Vibration API.
 * Gracefully no-ops on devices that don't support vibration.
 * Returns stable function references (safe for useEffect deps).
 */

function vibrateNativeOrWeb(pattern: number | number[]) {
    // 1. Native Android bridge
    if (typeof window !== 'undefined' && window.AndroidBridge?.vibrate) {
        try {
            const ms = Array.isArray(pattern) ? pattern.reduce((acc, v) => acc + v, 0) : pattern
            window.AndroidBridge.vibrate(ms)
            return
        } catch {
            // Fall back to navigator.vibrate if bridge throws
        }
    }

    // 2. Web Vibration API fallback
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
        navigator.vibrate(pattern)
    }
}

/** Light tap — selection, toggle (10ms) */
const tap = () => vibrateNativeOrWeb(10)

/** Medium tap — confirm action, button press (25ms) */
const press = () => vibrateNativeOrWeb(25)

/** Success pattern — scan found, listing created (50ms) */
const success = () => vibrateNativeOrWeb(50)

/** Error pattern — scan failed, validation error (two short pulses) */
const error = () => vibrateNativeOrWeb([25, 50, 25])

/** Warning pattern — destructive action about to happen */
const warning = () => vibrateNativeOrWeb([15, 30, 15, 30, 15])

const haptics = {
    tap,
    press,
    success,
    error,
    warning,
    get canVibrate() {
        return Boolean(
            (typeof window !== 'undefined' && window.AndroidBridge?.vibrate) ||
            (typeof navigator !== 'undefined' && 'vibrate' in navigator)
        )
    }
} as const

export function useHaptics() {
    return haptics
}
