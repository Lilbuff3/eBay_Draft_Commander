import { ChevronRight, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ToolCardProps {
    icon: LucideIcon
    title: string
    description: string
    color: string
    onClick?: () => void
}

export function ToolCard({ icon: Icon, title, description, color, onClick }: ToolCardProps) {
    return (
        <button
            onClick={onClick}
            className="flex flex-col items-start p-5 bg-white rounded-2xl border border-stone-100 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-300 group text-left w-full h-full"
        >
            <div
                className={cn(
                    'w-10 h-10 rounded-xl flex items-center justify-center text-white mb-4 shadow-sm group-hover:scale-110 transition-transform',
                    color
                )}
            >
                <Icon size={20} />
            </div>
            <h3 className="font-semibold text-stone-800 text-lg mb-1">{title}</h3>
            <p className="text-sm text-stone-400 font-light">{description}</p>
            <div className="mt-auto pt-4 flex items-center text-xs font-medium uppercase tracking-wider text-stone-300 group-hover:text-stone-600 transition-colors">
                Launch <ChevronRight size={12} className="ml-1" />
            </div>
        </button>
    )
}
