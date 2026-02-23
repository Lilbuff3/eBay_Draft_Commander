import { sanitizeDescription } from '@/lib/sanitizer'

interface ItemDescriptionCardProps {
    description?: string
}

export function ItemDescriptionCard({ description }: ItemDescriptionCardProps) {
    if (!description) {
        return null;
    }

    return (
        <div>
            <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-2 block">
                Description
            </label>
            <div className="bg-stone-50 rounded-xl p-3 border border-stone-100 max-h-32 overflow-y-auto">
                <div
                    className="text-sm text-stone-600 prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{
                        __html: sanitizeDescription(
                            description.slice(0, 500) +
                            (description.length > 500 ? '...' : '')
                        ).html
                    }}
                />
            </div>
        </div>
    )
}
