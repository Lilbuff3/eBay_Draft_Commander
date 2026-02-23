

interface ItemSpecificsCardProps {
    itemSpecifics?: Record<string, unknown>
}

export function ItemSpecificsCard({ itemSpecifics }: ItemSpecificsCardProps) {
    if (!itemSpecifics || Object.keys(itemSpecifics).length === 0) {
        return null;
    }

    return (
        <div>
            <label className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-2 block">
                Item Specifics
            </label>
            <div className="bg-stone-50 rounded-xl p-3 border border-stone-100">
                <div className="grid grid-cols-2 gap-2 text-sm">
                    {Object.entries(itemSpecifics).slice(0, 8).map(([key, value]) => (
                        <div key={key} className="flex gap-1">
                            <span className="text-stone-400 font-medium">{key}:</span>
                            <span className="text-stone-700 truncate">{String(value)}</span>
                        </div>
                    ))}
                </div>
                {Object.keys(itemSpecifics).length > 8 && (
                    <p className="text-[10px] text-stone-400 mt-2">
                        +{Object.keys(itemSpecifics).length - 8} more
                    </p>
                )}
            </div>
        </div>
    )
}
