import { useState } from 'react'
import { Package, Eye, Clock, Megaphone, XCircle, TrendingDown, ExternalLink, Loader2 } from 'lucide-react'
import type { Listing } from '@/components/ActiveListings'
import { ageDays, ageLabel, staleTag, TAG_META } from '@/lib/staleness'

interface InventoryCardProps {
    listing: Listing
    busy?: { price?: boolean; promote?: boolean; end?: boolean }
    onDropPrice: (listing: Listing, newPrice: number) => void
    onPromote: (listing: Listing) => void
    onEnd: (listing: Listing) => void
}

const DROP_PCTS = [10, 15, 20]

export function InventoryCard({ listing, busy, onDropPrice, onPromote, onEnd }: InventoryCardProps) {
    const [imgError, setImgError] = useState(false)
    const [showDrops, setShowDrops] = useState(false)

    const age = ageDays(listing.startTime)
    const watchers = listing.watchCount ?? 0
    const tag = staleTag(watchers, age)
    const meta = TAG_META[tag]
    const anyBusy = !!(busy?.price || busy?.promote || busy?.end)

    return (
        <div className="bg-paper-card backdrop-blur-2xl border border-stone-200 shadow-sm rounded-3xl p-3.5 hover:bg-paper-card transition duration-300">
            <div className="flex gap-3">
                {/* Photo */}
                <div className="w-16 h-16 rounded-xl bg-stone-50 overflow-hidden flex-shrink-0 border border-stone-200">
                    {listing.imageUrl && !imgError ? (
                        <img src={listing.imageUrl} alt="" className="w-full h-full object-cover"
                            loading="lazy" onError={() => setImgError(true)} />
                    ) : (
                        <div className="w-full h-full grid place-items-center text-stone-400">
                            <Package size={20} />
                        </div>
                    )}
                </div>

                {/* Title + signals */}
                <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-bold leading-snug text-ink-800 line-clamp-2">
                        {listing.title}
                    </div>
                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap text-[11px] font-medium">
                        <span className={`px-1.5 py-0.5 rounded-md ${meta.chip}`}>{meta.label}</span>
                        <span className="inline-flex items-center gap-1 text-stone-500">
                            <Clock size={11} strokeWidth={2} />{ageLabel(age)}
                        </span>
                        <span className="inline-flex items-center gap-1 text-stone-500">
                            <Eye size={11} strokeWidth={2} />{watchers}
                        </span>
                    </div>
                </div>

                {/* Price */}
                <div className="text-right flex-shrink-0">
                    <div className={`font-display font-bold text-[16px] tracking-[-0.02em] ${listing.price === 0 ? 'text-rose-600' : 'text-persimmon-600'}`}>
                        ${listing.price.toFixed(2)}
                    </div>
                    <a href={`https://www.ebay.com/itm/${listing.listingId}`} target="_blank" rel="noreferrer"
                        className="inline-flex items-center gap-1 min-h-[44px] px-1.5 -mr-1.5 rounded-lg text-xs text-stone-500 hover:text-persimmon-600 hover:bg-stone-100">
                        view <ExternalLink size={12} />
                    </a>
                </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1.5 mt-2.5">
                <button
                    onClick={() => setShowDrops(v => !v)}
                    disabled={anyBusy || listing.price <= 0}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 h-11 rounded-lg text-[12px] font-semibold
                               bg-persimmon-50 text-persimmon-700 border border-persimmon-200 hover:bg-persimmon-100
                               disabled:opacity-50 transition"
                >
                    {busy?.price ? <Loader2 size={13} className="animate-spin" /> : <TrendingDown size={13} />}
                    Drop price
                </button>
                <button
                    onClick={() => onPromote(listing)}
                    disabled={anyBusy}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 h-11 rounded-lg text-[12px] font-semibold
                               bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 disabled:opacity-50 transition"
                >
                    {busy?.promote ? <Loader2 size={13} className="animate-spin" /> : <Megaphone size={13} />}
                    Promote
                </button>
                <button
                    onClick={() => onEnd(listing)}
                    disabled={anyBusy}
                    className="inline-flex items-center justify-center gap-1.5 h-11 px-4 rounded-lg text-[12px] font-semibold
                               bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 disabled:opacity-50 transition"
                >
                    {busy?.end ? <Loader2 size={13} className="animate-spin" /> : <XCircle size={13} />}
                    End
                </button>
            </div>

            {/* Drop-price presets */}
            {showDrops && listing.price > 0 && (
                <div className="flex items-center gap-1.5 mt-2">
                    {DROP_PCTS.map(pct => {
                        const next = parseFloat((listing.price * (1 - pct / 100)).toFixed(2))
                        return (
                            <button
                                key={pct}
                                onClick={() => { setShowDrops(false); onDropPrice(listing, next) }}
                                disabled={anyBusy}
                                className="flex-1 h-11 rounded-lg text-[11.5px] font-semibold bg-stone-50/50 border border-stone-200
                                           text-persimmon-700 hover:bg-paper-card disabled:opacity-50 transition"
                            >
                                −{pct}% → ${next.toFixed(2)}
                            </button>
                        )
                    })}
                </div>
            )}
        </div>
    )
}
