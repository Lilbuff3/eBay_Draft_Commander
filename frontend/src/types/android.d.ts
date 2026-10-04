export interface AndroidBridge {
    vibrate(durationMs: number): void
    setKeepScreenOn(enabled: boolean): void
    showToast(message: string): void
    getAppVersion(): string
    getServerMode(): string
    openServerSettings(): void
    setApiKey?(key: string): void
    getApiKey?(): string
}

declare global {
    interface Window {
        AndroidBridge?: AndroidBridge
        isAndroidWrapper?: boolean
    }
}
