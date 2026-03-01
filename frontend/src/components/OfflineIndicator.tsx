import { useOnlineStatus } from '@/lib/offlineQueue'
import { WifiOff, CloudUpload, Check } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

export function OfflineIndicator() {
    const { isOnline, pendingCount, lastSyncUrl } = useOnlineStatus()

    // Don't render anything when online and nothing to show
    if (isOnline && pendingCount === 0 && !lastSyncUrl) {
        return null
    }

    return (
        <AnimatePresence>
            {/* Offline Banner */}
            {!isOnline && (
                <motion.div
                    initial={{ opacity: 0, y: -40 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -40 }}
                    className="fixed top-0 left-0 right-0 z-[60] flex items-center justify-center gap-2 py-2 px-4 bg-amber-600 text-white text-sm font-medium shadow-lg"
                >
                    <WifiOff className="w-4 h-4 flex-shrink-0" />
                    <span>
                        You're offline
                        {pendingCount > 0 && (
                            <> — {pendingCount} request{pendingCount > 1 ? 's' : ''} queued</>
                        )}
                    </span>
                </motion.div>
            )}

            {/* Pending sync indicator (online but still syncing) */}
            {isOnline && pendingCount > 0 && (
                <motion.div
                    initial={{ opacity: 0, y: -40 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -40 }}
                    className="fixed top-0 left-0 right-0 z-[60] flex items-center justify-center gap-2 py-2 px-4 bg-blue-600 text-white text-sm font-medium shadow-lg"
                >
                    <CloudUpload className="w-4 h-4 flex-shrink-0 animate-pulse" />
                    <span>
                        Syncing {pendingCount} queued request{pendingCount > 1 ? 's' : ''}…
                    </span>
                </motion.div>
            )}

            {/* Sync success toast */}
            {lastSyncUrl && (
                <motion.div
                    initial={{ opacity: 0, scale: 0.9, y: -20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.9, y: -20 }}
                    className="fixed top-2 right-2 md:right-4 z-[60] flex items-center gap-2 py-2 px-4 bg-emerald-600 text-white text-sm font-medium rounded-lg shadow-lg"
                >
                    <Check className="w-4 h-4 flex-shrink-0" />
                    <span>Synced successfully</span>
                </motion.div>
            )}
        </AnimatePresence>
    )
}
