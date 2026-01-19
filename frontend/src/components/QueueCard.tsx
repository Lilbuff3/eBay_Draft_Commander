import { motion } from 'framer-motion'
import { Clock, Loader2, Check, AlertCircle, Image } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import type { Job, JobStatus } from '@/lib/api'

interface QueueCardProps {
    job: Job
    isSelected: boolean
    onClick: () => void
}

const statusConfig: Record<JobStatus, { icon: typeof Clock; color: string; badgeVariant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
    pending: { icon: Clock, color: 'bg-stone-100 text-stone-500', badgeVariant: 'secondary' },
    processing: { icon: Loader2, color: 'bg-clay-400 text-white', badgeVariant: 'default' },
    completed: { icon: Check, color: 'bg-sage-100 text-sage-700', badgeVariant: 'outline' },
    failed: { icon: AlertCircle, color: 'bg-red-100 text-red-600', badgeVariant: 'destructive' },
}

export function QueueCard({ job, isSelected, onClick }: QueueCardProps) {
    const status = statusConfig[job.status] || statusConfig.pending
    const StatusIcon = status.icon
    const isProcessing = job.status === 'processing'

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            onClick={onClick}
            className={cn(
                'p-3 rounded-xl cursor-pointer transition-all duration-200 border',
                isSelected
                    ? 'bg-white border-sage-500 shadow-md ring-1 ring-sage-500'
                    : 'bg-white border-transparent hover:border-stone-200 hover:shadow-sm'
            )}
        >
            <div className="flex gap-3">
                {/* Thumbnail */}
                <div className="w-16 h-16 rounded-lg bg-stone-100 flex-shrink-0 overflow-hidden relative">
                    <div className="w-full h-full flex items-center justify-center text-stone-300">
                        <Image size={24} />
                    </div>
                    {/* Status Badge */}
                    <div className={cn('absolute bottom-0 right-0 p-1 rounded-tl-lg', status.color)}>
                        <StatusIcon size={12} className={isProcessing ? 'animate-spin' : ''} />
                    </div>
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-stone-800 text-sm truncate">{job.name}</h4>
                    <p className="text-xs text-stone-500 mt-1 truncate">
                        {job.listing_id ? `Active: ${job.listing_id}` : 'Draft not started'}
                    </p>

                    <div className="flex items-center gap-2 mt-2">
                        <Badge
                            variant={status.badgeVariant}
                            className="text-[10px] px-1.5 py-0.5 uppercase tracking-wider"
                        >
                            {job.status}
                        </Badge>
                    </div>
                </div>
            </div>
        </motion.div>
    )
}
