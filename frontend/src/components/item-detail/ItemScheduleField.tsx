import { CalendarClock } from 'lucide-react'
import { Input } from '@/components/ui/input'
import type { ItemDraft } from '@/lib/api'

interface ItemScheduleFieldProps {
    scheduledTime: string
    updateDraft: (updates: Partial<ItemDraft>) => void
}

// eBay requires 48 hours minimum lead time for scheduled listings
const MIN_LEAD_HOURS = 48
const MAX_LEAD_DAYS = 21

export function ItemScheduleField({ scheduledTime, updateDraft }: ItemScheduleFieldProps) {
    const now = new Date()
    const tzOffset = now.getTimezoneOffset() * 60000

    const minDate = new Date(now.getTime() + MIN_LEAD_HOURS * 60 * 60 * 1000 - tzOffset)
        .toISOString().slice(0, 16)
    const maxDate = new Date(now.getTime() + MAX_LEAD_DAYS * 24 * 60 * 60 * 1000 - tzOffset)
        .toISOString().slice(0, 16)

    return (
        <div className="p-3 bg-blue-50/50 rounded-xl border border-blue-100">
            <label htmlFor="listing-schedule" className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-1 block flex items-center gap-1">
                <CalendarClock size={12} />
                Schedule (Optional)
            </label>
            <Input
                id="listing-schedule"
                type="datetime-local"
                value={scheduledTime}
                min={minDate}
                max={maxDate}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateDraft({ scheduledTime: e.target.value })}
                className="bg-white"
            />
            <p className="text-[10px] text-stone-400 mt-1">
                Must be 48h+ from now. Leave blank to post immediately.
            </p>
        </div>
    )
}
