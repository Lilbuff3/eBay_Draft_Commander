import { useOnlineStatus } from '@/lib/offlineQueue'
import { useCommanderStore } from '@/store/useCommanderStore'
import { WifiOff, CloudUpload, Check, Upload } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function OfflineIndicator() {
    const { isOnline, pendingCount, lastSyncUrl } = useOnlineStatus()
    const uploadProgress = useCommanderStore(state => state.uploadProgress)

    // Don't render anything when online and nothing to show
    if (isOnline && pendingCount === 0 && !lastSyncUrl && !uploadProgress) {
        return null
    }

    const pct = uploadProgress
        ? Math.round((uploadProgress.loaded / uploadProgress.total) * 100)
        : 0

    return (
        <AnimatePresence>
            {/* Upload Progress Banner */}
            {uploadProgress && (
                <motion.div
                    key="upload-progress"
                    initial={{ opacity: 0, y: -40 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -40 }}
                    className="fixed top-0 left-0 right-0 z-[60] bg-blue-600 text-white shadow-lg"
                >
                    <div className="flex items-center justify-center gap-2 py-2 px-4 text-sm font-medium">
                        <Upload className="w-4 h-4 flex-shrink-0 animate-pulse" />
                        <span>
                            Uploading {uploadProgress.fileCount} photo{uploadProgress.fileCount > 1 ? 's' : ''}
                            {' '}&mdash; {pct}%
                            <span className="ml-1 text-blue-200 text-xs">
                                ({formatBytes(uploadProgress.loaded)} / {formatBytes(uploadProgress.total)})
                            </span>
                        </span>
                    </div>
                    {/* Progress bar */}
                    <div className="h-1 bg-blue-800">
                        <motion.div
                            className="h-full bg-blue-300"
                            initial={{ width: 0 }}
                            animate={{ width: `${pct}%` }}
                            transition={{ duration: 0.3, ease: 'easeOut' }}
                        />
                    </div>
                </motion.div>
            )}

            {/* Offline Banner */}
            {!isOnline && !uploadProgress && (
                <motion.div
                    key="offline"
                    initial={{ opacity: 0, y: -40 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -40 }}
                    className="fixed top-0 left-0 right-0 z-[60] flex items-center justify-center gap-2 py-2 px-4 bg-amber-600 text-white text-sm font-medium shadow-lg"
                >
                    <WifiOff className="w-4 h-4 flex-shrink-0" />
                    <span>
                        You're offline
                        {pendingCount > 0 && (
                            <> &mdash; {pendingCount} request{pendingCount > 1 ? 's' : ''} queued</>
                        )}
                    </span>
                </motion.div>
            )}

            {/* Pending sync indicator (online but still syncing) */}
            {isOnline && pendingCount > 0 && !uploadProgress && (
                <motion.div
                    key="syncing"
                    initial={{ opacity: 0, y: -40 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -40 }}
                    className="fixed top-0 left-0 right-0 z-[60] flex items-center justify-center gap-2 py-2 px-4 bg-blue-600 text-white text-sm font-medium shadow-lg"
                >
                    <CloudUpload className="w-4 h-4 flex-shrink-0 animate-pulse" />
                    <span>
                        Syncing {pendingCount} queued request{pendingCount > 1 ? 's' : ''}...
                    </span>
                </motion.div>
            )}

            {/* Sync success toast */}
            {lastSyncUrl && (
                <motion.div
                    key="sync-success"
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
