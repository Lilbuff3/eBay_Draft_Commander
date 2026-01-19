import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

export enum WorkflowStage {
    IMPORT = 0,
    ANALYZE = 1,
    EDIT = 2,
    PRICE = 3,
    POST = 4,
}

interface StageProgressProps {
    currentStage: WorkflowStage
    onStageClick?: (stage: WorkflowStage) => void
}

const stages = [
    { id: WorkflowStage.IMPORT, label: 'Import' },
    { id: WorkflowStage.ANALYZE, label: 'Analyze' },
    { id: WorkflowStage.EDIT, label: 'Edit' },
    { id: WorkflowStage.PRICE, label: 'Price' },
    { id: WorkflowStage.POST, label: 'Post' },
]

export function StageProgress({ currentStage, onStageClick }: StageProgressProps) {
    const currentIndex = currentStage

    return (
        <div className="w-full py-4 px-6 mb-2">
            <div className="relative flex justify-between items-center">
                {/* Progress Line Background */}
                <div className="absolute top-1/2 left-0 w-full h-0.5 bg-stone-200 -z-10 rounded-full" />

                {/* Active Progress Line */}
                <div
                    className="absolute top-1/2 left-0 h-0.5 bg-sage-500 -z-10 rounded-full transition-all duration-500"
                    style={{ width: `${(currentIndex / (stages.length - 1)) * 100}%` }}
                />

                {stages.map((stage, idx) => {
                    const isCompleted = idx <= currentIndex
                    const isActive = idx === currentIndex

                    return (
                        <button
                            key={stage.id}
                            onClick={() => onStageClick?.(stage.id)}
                            className="flex flex-col items-center gap-2 group"
                        >
                            <div
                                className={cn(
                                    'w-8 h-8 rounded-full flex items-center justify-center border-2 z-10 transition-all duration-300 bg-stone-50',
                                    isCompleted
                                        ? 'border-sage-500 bg-sage-500 text-white'
                                        : 'border-stone-300 text-stone-400',
                                    isActive && 'ring-4 ring-sage-100 scale-110',
                                    onStageClick && 'cursor-pointer hover:scale-105'
                                )}
                            >
                                {idx < currentIndex ? (
                                    <Check size={14} />
                                ) : (
                                    <span className="text-sm font-medium">{idx + 1}</span>
                                )}
                            </div>
                            <span
                                className={cn(
                                    'text-xs font-medium transition-colors',
                                    isActive ? 'text-sage-700' : 'text-stone-400'
                                )}
                            >
                                {stage.label}
                            </span>
                        </button>
                    )
                })}
            </div>
        </div>
    )
}
