import { describe, it, expect, beforeEach } from 'vitest'
import { isAppInstalled } from './pwa'

describe('pwa isAppInstalled', () => {
    beforeEach(() => {
        delete window.isAndroidWrapper
        delete window.AndroidBridge
    })

    it('returns true when window.isAndroidWrapper is true', () => {
        window.isAndroidWrapper = true
        expect(isAppInstalled()).toBe(true)
    })

    it('returns true when window.AndroidBridge is defined', () => {
        window.AndroidBridge = {
            vibrate: () => {},
            setKeepScreenOn: () => {},
            showToast: () => {},
            getAppVersion: () => '1.0.0',
            getServerMode: () => 'TAILSCALE',
            openServerSettings: () => {},
        }
        expect(isAppInstalled()).toBe(true)
    })

    it('returns false by default in standard browser environment', () => {
        expect(isAppInstalled()).toBe(false)
    })
})
