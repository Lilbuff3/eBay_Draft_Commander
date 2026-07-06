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
        <div className="bg-slate-900/40 backdrop-blur-2xl border border-white/5 shadow-glass rounded-3xl p-3.5 hover:bg-slate-900/60 transition duration-300">
            <div className="flex gap-3">
                {/* Photo */}
                <div className="w-16 h-16 rounded-xl bg-slate-950/40 overflow-hidden flex-shrink-0 border border-white/10">
                    {listing.imageUrl && !imgError ? (
                        <img src={listing.imageUrl} alt="" className="w-full h-full object-cover"
                            loading="lazy" onError={() => setImgError(true)} />
                    ) : (
                        <div className="w-full h-full grid place-items-center text-slate-600">
                            <Package size={20} />
                        </div>
                    )}
                </div>

                {/* Title + signals */}
                <div className="min-w-0 flex-1">
                    <div className="text-[13px] font-bold leading-snug text-white line-clamp-2">
                        {listing.title}
                    </div>
                    <div className="flex items-center gap-1.5 mt-1.5 flex-wrap text-[11px] font-medium">
                        <span className={`px-1.5 py-0.5 rounded-md ${meta.chip}`}>{meta.label}</span>
                        <span className="inline-flex items-center gap-1 text-slate-400">
                            <Clock size={11} strokeWidth={2} />{ageLabel(age)}
                        </span>
                        <span className="inline-flex items-center gap-1 text-slate-400">
                            <Eye size={11} strokeWidth={2} />{watchers}
                        </span>
                    </div>
                </div>

                {/* Price */}
                <div className="text-right flex-shrink-0">
                    <div className={`font-display font-bold text-[16px] tracking-[-0.02em] ${listing.price === 0 ? 'text-rose-400' : 'text-brand-400'}`}>
                        ${listing.price.toFixed(2)}
                    </div>
                    <a href={`https://www.ebay.com/itm/${listing.listingId}`} target="_blank" rel="noreferrer"
                        className="inline-flex items-center gap-0.5 text-[10.5px] text-slate-500 hover:text-brand-400 mt-0.5">
                        view <ExternalLink size={10} />
                    </a>
                </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1.5 mt-2.5">
                <button
                    onClick={() => setShowDrops(v => !v)}
                    disabled={anyBusy || listing.price <= 0}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 h-8 rounded-lg text-[12px] font-semibold
                               bg-brand-500/10 text-brand-300 border border-brand-500/20 hover:bg-brand-500/20
                               disabled:opacity-50 transition"
                >
                    {busy?.price ? <Loader2 size={13} className="animate-spin" /> : <TrendingDown size={13} />}
                    Drop price
                </button>
                <button
                    onClick={() => onPromote(listing)}
                    disabled={anyBusy}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 h-8 rounded-lg text-[12px] font-semibold
                               bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 hover:bg-emerald-500/20 disabled:opacity-50 transition"
                >
                    {busy?.promote ? <Loader2 size={13} className="animate-spin" /> : <Megaphone size={13} />}
                    Promote
                </button>
                <button
                    onClick={() => onEnd(listing)}
                    disabled={anyBusy}
                    className="inline-flex items-center justify-center gap-1.5 h-8 px-3 rounded-lg text-[12px] font-semibold
                               bg-rose-500/10 text-rose-300 border border-rose-500/20 hover:bg-rose-500/20 disabled:opacity-50 transition"
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
                                className="flex-1 h-8 rounded-lg text-[11.5px] font-semibold bg-slate-950/50 border border-white/10
                                           text-brand-300 hover:bg-slate-900 disabled:opacity-50 transition"
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
