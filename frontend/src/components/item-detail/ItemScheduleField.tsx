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

/** Find the next occurrence of a target day/hour in UTC */
function getNextOptimalSlot(targetDay: number, targetHourUTC: number): Date {
    const now = new Date()
    const target = new Date(now)
    target.setUTCHours(targetHourUTC, 0, 0, 0)

    // Find next occurrence of target day (0=Sun, 1=Mon, etc.)
    const daysUntil = (targetDay - now.getUTCDay() + 7) % 7
    target.setUTCDate(now.getUTCDate() + (daysUntil === 0 && now > target ? 7 : daysUntil))

    return target
}

function getSchedulePresets(): Array<{ label: string; value: string; sublabel: string }> {
    // Sunday 7PM Pacific = ~03:00 UTC (approximate, DST-aware via local formatting)
    const sundayEvening = getNextOptimalSlot(0, 3)   // Sunday ~7PM PT
    const mondayEvening = getNextOptimalSlot(1, 3)    // Monday ~7PM PT
    const wednesdayEvening = getNextOptimalSlot(3, 3) // Wed ~7PM PT

    const fmt = (d: Date) => {
        return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }) +
            ' ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    }

    return [
        { label: 'Sun Evening', sublabel: fmt(sundayEvening), value: sundayEvening.toISOString() },
        { label: 'Mon Evening', sublabel: fmt(mondayEvening), value: mondayEvening.toISOString() },
        { label: 'Wed Evening', sublabel: fmt(wednesdayEvening), value: wednesdayEvening.toISOString() },
    ]
}

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
            <div className="flex gap-1.5 mb-2">
                {getSchedulePresets().map((preset) => (
                    <button
                        key={preset.label}
                        type="button"
                        onClick={() => updateDraft({ scheduledTime: preset.value })}
                        className="flex-1 px-2 py-1.5 text-xs leading-tight text-center rounded-md border border-stone-200 hover:border-blue-400 hover:bg-blue-50 transition-colors"
                    >
                        <div className="font-semibold">{preset.label}</div>
                        <div className="text-stone-400">{preset.sublabel}</div>
                    </button>
                ))}
            </div>
            <Input
                id="listing-schedule"
                type="datetime-local"
                value={scheduledTime}
                min={minDate}
                max={maxDate}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateDraft({ scheduledTime: e.target.value })}
                className="bg-white"
            />
            <p className="text-xs text-stone-400 mt-1">
                Must be 48h+ from now. Leave blank to post immediately.
            </p>
        </div>
    )
}
