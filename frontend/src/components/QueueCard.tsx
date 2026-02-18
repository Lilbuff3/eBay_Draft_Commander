import { motion } from 'framer-motion'
import { Clock, Loader2, Check, AlertCircle, Image, Square, CheckSquare, CalendarClock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import type { Job, JobStatus } from '@/lib/api'

interface QueueCardProps {
    job: Job
    isSelected: boolean
    isSelectionMode: boolean
    onToggleSelect: (id: string) => void
    onClick: () => void
}

const statusConfig: Record<JobStatus, { icon: typeof Clock; color: string; badgeVariant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
    pending: { icon: Clock, color: 'bg-stone-100 text-stone-500', badgeVariant: 'secondary' },
    processing: { icon: Loader2, color: 'bg-clay-400 text-white', badgeVariant: 'default' },
    completed: { icon: Check, color: 'bg-sage-100 text-sage-700', badgeVariant: 'outline' },
    failed: { icon: AlertCircle, color: 'bg-red-100 text-red-600', badgeVariant: 'destructive' },
    scheduled: { icon: CalendarClock, color: 'bg-blue-100 text-blue-600', badgeVariant: 'secondary' },
}

export function QueueCard({ job, isSelected, isSelectionMode, onToggleSelect, onClick }: QueueCardProps) {
    const status = statusConfig[job.status] || statusConfig.pending
    const StatusIcon = status.icon
    const isProcessing = job.status === 'processing'

    const handleCardClick = (e: React.MouseEvent) => {
        if (isSelectionMode) {
            e.stopPropagation()
            onToggleSelect(job.id)
        } else {
            onClick()
        }
    }

    // Format scheduled time for display
    const scheduledDate = job.scheduled_time ? new Date(job.scheduled_time) : null
    const isScheduledFuture = scheduledDate && scheduledDate > new Date()

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            onClick={handleCardClick}
            className={cn(
                'p-3 rounded-xl cursor-pointer relative group transition-all',
                isSelected && !isSelectionMode
                    ? 'glass-card border-sage-500 ring-2 ring-sage-500/20 bg-white/90'
                    : 'glass-card hover:translate-y-[-2px]',
                isSelectionMode && isSelected && 'bg-blue-50 border-blue-200'
            )}
        >
            <div className="flex gap-3">
                {/* Selection Checkbox (Visible in Mode OR on Hover) */}
                <div
                    className={cn(
                        "flex items-center justify-center transition-all duration-200",
                        isSelectionMode ? "w-6 opacity-100 mr-1" : "w-0 opacity-0 overflow-hidden group-hover:w-6 group-hover:opacity-100 group-hover:mr-1"
                    )}
                    onClick={(e) => {
                        e.stopPropagation()
                        onToggleSelect(job.id)
                    }}
                >
                    {isSelectionMode && isSelected ? (
                        <CheckSquare size={20} className="text-blue-600" />
                    ) : (
                        <Square size={20} className="text-stone-300 hover:text-stone-400" />
                    )}
                </div>

                {/* Thumbnail */}
                <div className="w-16 h-16 rounded-lg bg-stone-100 flex-shrink-0 overflow-hidden relative">
                    {job.thumbnail_url ? (
                        <img
                            src={job.thumbnail_url}
                            alt={job.name}
                            className="w-full h-full object-cover"
                        />
                    ) : (
                        <div className="w-full h-full flex items-center justify-center text-stone-300">
                            <Image size={24} />
                        </div>
                    )}
                    {/* Status Badge */}
                    <div className={cn('absolute bottom-0 right-0 p-1 rounded-tl-lg', status.color)}>
                        <StatusIcon size={12} className={isProcessing ? 'animate-spin' : ''} />
                    </div>
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-stone-800 text-sm truncate">{job.name}</h4>
                    <p className="text-xs text-stone-500 mt-1 truncate">
                        {isScheduledFuture ? `Scheduled: ${scheduledDate?.toLocaleDateString()} ${scheduledDate?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` :
                            job.listing_id ? `Active: ${job.listing_id}` :
                                job.status === 'completed' ? 'Draft Ready' :
                                    job.status === 'processing' ? 'Analyzing...' :
                                        job.status === 'failed' ? 'Issue Detected' :
                                            'Pending'}
                    </p>

                    <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <Badge
                            variant={status.badgeVariant}
                            className="text-[10px] px-1.5 py-0.5 uppercase tracking-wider"
                        >
                            {job.status}
                        </Badge>

                        {job.condition && (
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0.5 bg-yellow-50 text-yellow-700 border-yellow-200">
                                {job.condition}
                            </Badge>
                        )}

                        {job.price && (
                            <Badge variant="secondary" className="text-[10px] px-1.5 py-0.5 bg-green-50 text-green-700">
                                ${job.price}
                            </Badge>
                        )}
                    </div>

                    {job.error_type && (
                        <div className="mt-2 text-[10px] text-red-500 bg-red-50 p-1 rounded border border-red-100 truncate" title={job.error_message || ''}>
                            {job.error_type}
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    )
}
