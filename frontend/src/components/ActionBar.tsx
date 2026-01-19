import { Play, Pause, Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface ActionBarProps {
    isProcessing: boolean
    onStart: () => void
    onPause: () => void
    onSettings: () => void
}

export function ActionBar({ isProcessing, onStart, onPause, onSettings }: ActionBarProps) {
    return (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-stone-900/90 backdrop-blur-md text-white px-6 py-3 rounded-2xl shadow-2xl flex items-center gap-6 z-50 border border-white/10">
            {/* Status */}
            <div className="flex items-center gap-4 border-r border-white/20 pr-6">
                <div className="flex flex-col text-right">
                    <span className="text-xs text-stone-400 uppercase tracking-wider font-bold">
                        Status
                    </span>
                    <span className={cn('font-medium', isProcessing ? 'text-sage-400' : 'text-white')}>
                        {isProcessing ? 'Processing Queue' : 'Ready to Start'}
                    </span>
                </div>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-3">
                {!isProcessing ? (
                    <Button
                        onClick={onStart}
                        className="bg-white text-stone-900 hover:bg-sage-50 font-bold"
                    >
                        <Play size={18} className="mr-2 fill-stone-900" />
                        Start Queue
                    </Button>
                ) : (
                    <Button
                        onClick={onPause}
                        className="bg-clay-500 hover:bg-clay-600 text-white font-bold"
                    >
                        <Pause size={18} className="mr-2 fill-white" />
                        Pause
                    </Button>
                )}

                <Button
                    variant="ghost"
                    size="icon"
                    onClick={onSettings}
                    className="text-stone-400 hover:text-white hover:bg-white/10"
                >
                    <Settings size={20} />
                </Button>
            </div>
        </div>
    )
}
