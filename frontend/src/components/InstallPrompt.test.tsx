import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render } from '@testing-library/react'
import { InstallPrompt } from './InstallPrompt'

describe('InstallPrompt', () => {
    beforeEach(() => {
        delete window.isAndroidWrapper
        delete window.AndroidBridge
        Object.defineProperty(window, 'matchMedia', {
            writable: true,
            value: vi.fn().mockImplementation(query => ({
                matches: false,
                media: query,
                onchange: null,
                addListener: vi.fn(),
                removeListener: vi.fn(),
                addEventListener: vi.fn(),
                removeEventListener: vi.fn(),
                dispatchEvent: vi.fn(),
            }))
        })
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('suppresses prompt when window.isAndroidWrapper is true', () => {
        window.isAndroidWrapper = true
        const { container } = render(<InstallPrompt />)
        expect(container.firstChild).toBeNull()
    })

    it('suppresses prompt when window.AndroidBridge is present', () => {
        window.AndroidBridge = {
            vibrate: () => {},
            setKeepScreenOn: () => {},
            showToast: () => {},
            getAppVersion: () => '1.0.0',
            getServerMode: () => 'TAILSCALE',
            openServerSettings: () => {},
        }
        const { container } = render(<InstallPrompt />)
        expect(container.firstChild).toBeNull()
    })
})
