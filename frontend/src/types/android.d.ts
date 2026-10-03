export interface AndroidBridge {
    vibrate(durationMs: number): void
    setKeepScreenOn(enabled: boolean): void
    showToast(message: string): void
    getAppVersion(): string
    getServerMode(): string
    openServerSettings(): void
}

declare global {
    interface Window {
        AndroidBridge?: AndroidBridge
        isAndroidWrapper?: boolean
    }
}
