interface ItemDescriptionCardProps {
    /** draft description (HTML source) — editable, submitted as user_description */
    value: string
    onChange: (value: string) => void
}

/**
 * Editable description. The value is HTML source (the AI writes description_html);
 * the drawer's Live Preview tab renders it properly, so this stays a plain
 * textarea rather than a rich editor. text-base keeps iOS from zooming on focus.
 */
export function ItemDescriptionCard({ value, onChange }: ItemDescriptionCardProps) {
    if (!value && value !== '') return null

    return (
        <div>
            <label htmlFor="listing-description" className="text-xs font-bold text-stone-400 uppercase tracking-wider mb-2 block">
                Description
            </label>
            <textarea
                id="listing-description"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder="Describe the item — condition details, flaws, what's included…"
                className="w-full min-h-40 rounded-xl border border-stone-200 bg-stone-50 focus:bg-white p-3 text-base md:text-sm text-stone-700 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] resize-y"
            />
            <p className="text-xs text-stone-500 mt-1.5">Edits here go live with the listing — check the Live Preview tab for the rendered version.</p>
        </div>
    )
}
