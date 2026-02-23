/**
 * useHaptics - Lightweight haptic feedback hook for Android
 * 
 * Uses the Vibration API to provide tactile feedback on mobile.
 * Gracefully no-ops on devices that don't support vibration.
 */

export function useHaptics() {
    const canVibrate = typeof navigator !== 'undefined' && 'vibrate' in navigator

    /** Light tap — selection, toggle (10ms) */
    const tap = () => {
        if (canVibrate) navigator.vibrate(10)
    }

    /** Medium tap — confirm action, button press (25ms) */
    const press = () => {
        if (canVibrate) navigator.vibrate(25)
    }

    /** Success pattern — scan found, listing created (50ms) */
    const success = () => {
        if (canVibrate) navigator.vibrate(50)
    }

    /** Error pattern — scan failed, validation error (two short pulses) */
    const error = () => {
        if (canVibrate) navigator.vibrate([25, 50, 25])
    }

    /** Warning pattern — destructive action about to happen */
    const warning = () => {
        if (canVibrate) navigator.vibrate([15, 30, 15, 30, 15])
    }

    return { tap, press, success, error, warning, canVibrate }
}
