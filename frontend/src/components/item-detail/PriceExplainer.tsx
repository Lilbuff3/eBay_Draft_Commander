import { useState } from 'react'
import { ExternalLink, ImageOff } from 'lucide-react'
import type { JobDetails, PricingComp } from '@/lib/api'

/**
 * "Why this price" — Vendit-style pricing transparency card.
 *
 * Range bar spans the comps' asking-price spread with the median marked;
 * below it, the actual comparable listings with photos. Comps come from the
 * Browse API (ACTIVE asking prices, not sold), so the copy says so — the
 * engine already discounts toward sold value via ACTIVE_TO_SOLD_FACTOR.
 * Renders nothing for AI-estimate paths (no comps, no range).
 */

function CompThumb({ comp }: { comp: PricingComp }) {
    const [failed, setFailed] = useState(false)
    if (!comp.image_url || failed) {
        return (
            <div className="w-14 h-14 shrink-0 rounded-lg bg-stone-100 border border-stone-200 grid place-items-center text-stone-300">
                <ImageOff size={18} />
            </div>
        )
    }
    return (
        <img
            src={comp.image_url}
            alt=""
            loading="lazy"
            onError={() => setFailed(true)}
            className="w-14 h-14 shrink-0 rounded-lg object-cover bg-stone-100 border border-stone-200"
        />
    )
}

interface PriceExplainerProps {
    pricing: JobDetails['pricing_data']
    /** current draft price, as typed in the input */
    price: string
}

export function PriceExplainer({ pricing, price }: PriceExplainerProps) {
    const comps = pricing?.comps ?? []
    const range = pricing?.price_range
    const hasRange = Array.isArray(range) && range.length === 2 && range[1] > 0
    if (comps.length === 0 && !hasRange) return null

    const low = hasRange ? range![0] : Math.min(...comps.map(c => c.price))
    const high = hasRange ? range![1] : Math.max(...comps.map(c => c.price))
    const median = pricing?.median_price ?? null
    const yourPrice = parseFloat(price) || 0
    const compCount = pricing?.comp_count ?? comps.length

    // Position 0..100% along the low→high spread, clamped to the bar
    const pct = (v: number) => {
        if (high <= low) return 50
        return Math.min(100, Math.max(0, ((v - low) / (high - low)) * 100))
    }

    const confidence = pricing?.pricing_confidence

    return (
        <div className="rounded-2xl border border-stone-200 bg-white p-4 space-y-3">
            <div className="flex items-baseline justify-between gap-2">
                <h4 className="text-xs font-bold text-stone-400 uppercase tracking-wider">Why this price</h4>
                <span className="text-xs text-stone-400">
                    {compCount} live listing{compCount !== 1 ? 's' : ''} · asking prices
                </span>
            </div>

            {/* Range bar: comp spread with median + your price markers */}
            {high > low && (
                <div className="pt-3 pb-1">
                    <div className="relative h-1.5 rounded-full bg-gradient-to-r from-sage-100 via-amber-200 to-amber-300">
                        {median !== null && (
                            <div
                                className="absolute -top-[3px] w-3 h-3 rounded-full bg-sage-600 border-2 border-white shadow"
                                style={{ left: `calc(${pct(median)}% - 6px)` }}
                                title={`Comp median $${median.toFixed(2)}`}
                            />
                        )}
                        {yourPrice > 0 && (
                            <div
                                className="absolute -top-2 h-[22px] w-0.5 bg-persimmon-600 rounded"
                                style={{ left: `${pct(yourPrice)}%` }}
                                title={`Your price $${yourPrice.toFixed(2)}`}
                            />
                        )}
                    </div>
                    <div className="flex justify-between mt-1.5 text-xs font-medium text-stone-500">
                        <span>${low.toFixed(0)}</span>
                        {median !== null && (
                            <span className="text-sage-700">median ${median.toFixed(2)}</span>
                        )}
                        <span>${high.toFixed(0)}</span>
                    </div>
                </div>
            )}

            {pricing?.reasoning && (
                <p className="text-xs text-stone-500">{pricing.reasoning}</p>
            )}
            {confidence === 'low' && pricing?.pricing_confidence_reason && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5">
                    Rough estimate — {pricing.pricing_confidence_reason}
                </p>
            )}

            {/* Comparable listings */}
            {comps.length > 0 && (
                <div className="space-y-2">
                    {comps.map((comp, i) => (
                        <a
                            key={i}
                            href={comp.url || undefined}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-3 rounded-xl border border-stone-200 bg-stone-50 p-2 hover:border-stone-300 hover:bg-white transition-colors"
                        >
                            <CompThumb comp={comp} />
                            <div className="flex-1 min-w-0">
                                <div className="text-sm text-stone-700 leading-snug line-clamp-2">{comp.title}</div>
                                {comp.condition && (
                                    <div className="text-xs text-stone-400 mt-0.5">{comp.condition}</div>
                                )}
                            </div>
                            <div className="shrink-0 text-right">
                                <div className="text-sm font-bold text-sage-700">${comp.price.toFixed(2)}</div>
                                {comp.url && <ExternalLink size={12} className="ml-auto mt-1 text-stone-300" />}
                            </div>
                        </a>
                    ))}
                </div>
            )}
        </div>
    )
}
