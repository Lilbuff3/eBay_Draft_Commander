import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useHaptics } from './useHaptics'

describe('useHaptics', () => {
    const originalNavigator = globalThis.navigator

    beforeEach(() => {
        delete window.AndroidBridge
        delete window.isAndroidWrapper
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('calls window.AndroidBridge.vibrate when bridge is present', () => {
        const mockBridgeVibrate = vi.fn()
        const mockNavVibrate = vi.fn()

        window.AndroidBridge = {
            vibrate: mockBridgeVibrate,
            setKeepScreenOn: vi.fn(),
            showToast: vi.fn(),
            getAppVersion: () => '1.0.0',
            getServerMode: () => 'TAILSCALE',
            openServerSettings: vi.fn(),
        }
        Object.defineProperty(globalThis, 'navigator', {
            value: { ...originalNavigator, vibrate: mockNavVibrate },
            configurable: true,
            writable: true,
        })

        const haptics = useHaptics()
        expect(haptics.canVibrate).toBe(true)

        haptics.tap()
        expect(mockBridgeVibrate).toHaveBeenCalledWith(10)
        expect(mockNavVibrate).not.toHaveBeenCalled()

        haptics.press()
        expect(mockBridgeVibrate).toHaveBeenCalledWith(25)

        haptics.success()
        expect(mockBridgeVibrate).toHaveBeenCalledWith(50)

        haptics.error()
        // [25, 50, 25] -> sum is 100
        expect(mockBridgeVibrate).toHaveBeenCalledWith(100)
    })

    it('falls back to navigator.vibrate when AndroidBridge is absent', () => {
        const mockNavVibrate = vi.fn()
        Object.defineProperty(globalThis, 'navigator', {
            value: { ...originalNavigator, vibrate: mockNavVibrate },
            configurable: true,
            writable: true,
        })

        const haptics = useHaptics()
        expect(haptics.canVibrate).toBe(true)

        haptics.tap()
        expect(mockNavVibrate).toHaveBeenCalledWith(10)

        haptics.error()
        expect(mockNavVibrate).toHaveBeenCalledWith([25, 50, 25])
    })

    it('falls back to navigator.vibrate if AndroidBridge.vibrate throws', () => {
        const mockNavVibrate = vi.fn()
        window.AndroidBridge = {
            vibrate: vi.fn().mockImplementation(() => {
                throw new Error('Bridge invocation failed')
            }),
            setKeepScreenOn: vi.fn(),
            showToast: vi.fn(),
            getAppVersion: () => '1.0.0',
            getServerMode: () => 'TAILSCALE',
            openServerSettings: vi.fn(),
        }
        Object.defineProperty(globalThis, 'navigator', {
            value: { ...originalNavigator, vibrate: mockNavVibrate },
            configurable: true,
            writable: true,
        })

        const haptics = useHaptics()
        haptics.tap()
        expect(mockNavVibrate).toHaveBeenCalledWith(10)
    })
})
