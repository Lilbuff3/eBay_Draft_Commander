import { useRef, useEffect } from 'react'
import { Terminal, XCircle, Activity } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

export interface LogEntry {
    job_id: string
    message: string
    level: 'info' | 'error' | 'warning' | 'success'
    timestamp: string
}

interface LogViewerProps {
    logs: LogEntry[]
    className?: string
    autoScroll?: boolean
}

export function LogViewer({ logs, className, autoScroll = true }: LogViewerProps) {
    const scrollRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        if (autoScroll && scrollRef.current) {
            const scrollContainer = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]')
            if (scrollContainer) {
                scrollContainer.scrollTop = scrollContainer.scrollHeight
            }
        }
    }, [logs, autoScroll])

    if (logs.length === 0) {
        return (
            <div className={cn("bg-stone-50 rounded-lg border border-stone-200 p-8 flex flex-col items-center justify-center text-stone-500", className)}>
                <Terminal size={32} className="mb-2 opacity-50" />
                <p className="text-sm font-mono">Waiting for logs...</p>
            </div>
        )
    }

    return (
        <div className={cn("bg-stone-50 rounded-lg border border-stone-200 flex flex-col overflow-hidden font-mono text-xs shadow-inner", className)}>
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-paper-card border-b border-stone-200">
                <div className="flex items-center gap-2 text-stone-500">
                    <Activity size={14} className="text-blue-500 animate-pulse" />
                    <span className="font-semibold">Live Activity Log</span>
                </div>
                <span className="text-[10px] text-stone-400">{logs.length} events</span>
            </div>

            <ScrollArea className="flex-1 p-4" ref={scrollRef}>
                <div className="space-y-1.5">
                    {logs.map((log, i) => (
                        <div key={i} className="flex gap-3 group">
                            <span className="text-stone-400 shrink-0 select-none w-16 text-right">
                                {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                            </span>
                            <div className={cn(
                                "break-all",
                                log.level === 'error' && "text-red-600",
                                log.level === 'warning' && "text-amber-600",
                                log.level === 'success' && "text-emerald-600 font-medium",
                                log.level === 'info' && "text-stone-600"
                            )}>
                                {log.level === 'error' && <XCircle size={12} className="inline mr-1.5 -mt-0.5" />}
                                {log.message}
                            </div>
                        </div>
                    ))}
                    {/* Spacer for auto-scroll visibility */}
                    <div className="h-2" />
                </div>
            </ScrollArea>
        </div>
    )
}
