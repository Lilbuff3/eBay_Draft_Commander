import { useQuery } from '@tanstack/react-query'
import { Search, ScanLine } from 'lucide-react'
import { fetchJobs } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'
import { useCommanderStore } from '@/store/useCommanderStore'
import { UploadZone } from '@/components/UploadZone'
import { ScoreboardStats } from './ScoreboardStats'
import { WorkspaceCard } from './WorkspaceCard'
import { ActivityRail } from './ActivityRail'

/**
 * DashboardHome — redesigned desktop home.
 *
 * Drop-in replacement for the scrollable content inside pages/Dashboard.tsx.
 * Keep the existing <ItemDetailDrawer>, <ConfirmDialog>, etc. from Dashboard;
 * this component only re-skins the home surface (header + stats + dropzone +
 * workspace grid + live activity rail). Wire `onSelectJob` to the store's
 * setSelectedJob so the existing drawer still opens.
 *
 * All data is REAL:
 *   - stats        ← ScoreboardStats (analytics + status endpoints)
 *   - jobs/photos  ← fetchJobs (thumbnail_url)
 *   - scan         ← store.handleScan  →  POST /api/scan
 *   - upload       ← <UploadZone> (existing) → POST /api/upload
 *   - activity     ← ActivityRail (derived from jobs)
 */
export function DashboardHome({ userName = 'there' }: { userName?: string }) {
    const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs, refetchInterval: 4000 })

    const setSelectedJob = useCommanderStore(s => s.setSelectedJob)
    const handleScan = useCommanderStore(s => s.handleScan)
    const isScanning = useCommanderStore(s => s.isScanning)

    const hr = new Date().getHours()
    const part = hr < 12 ? 'morning' : hr < 18 ? 'afternoon' : 'evening'
    const dateEyebrow = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })

    const counts = {
        all: jobs.length,
        needs: jobs.filter(j => getStatusBucket(j.status) === 'needs_you').length,
        working: jobs.filter(j => getStatusBucket(j.status) === 'working').length,
        live: jobs.filter(j => getStatusBucket(j.status) === 'live').length,
    }

    return (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-5">
            {/* Header */}
            <header className="flex items-center gap-4 flex-wrap">
                <div className="flex-1 min-w-[230px]">
                    <div className="text-[11px] font-semibold tracking-wide text-stone-400 uppercase">{dateEyebrow}</div>
                    <h1 className="font-display font-bold text-[27px] tracking-[-0.03em] leading-none text-ink-800 mt-1">
                        Good {part}, {userName}
                    </h1>
                </div>
                <div className="flex items-center gap-2">
                    <div className="relative w-[210px] hidden sm:block">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-[15px] h-[15px] text-stone-400" strokeWidth={1.8} />
                        <input
                            placeholder="Search items, listings…"
                            className="w-full h-[38px] pl-8 pr-3 rounded-[10px] border border-stone-200 bg-white text-[13px]
                                       text-ink-800 outline-none transition
                                       focus:border-persimmon-400 focus:ring-[3px] focus:ring-persimmon-400/[0.14]"
                        />
                    </div>
                    <button
                        onClick={handleScan}
                        disabled={isScanning}
                        className="flex items-center gap-2 h-[38px] px-3.5 rounded-[10px] border border-stone-200 bg-white
                                   text-[13px] font-semibold text-ink-700 transition hover:border-stone-300
                                   focus:border-persimmon-400 focus:ring-[3px] focus:ring-persimmon-400/[0.14] outline-none
                                   disabled:opacity-60"
                    >
                        <ScanLine className="w-[15px] h-[15px] text-stone-500" strokeWidth={1.8} />
                        {isScanning ? 'Scanning…' : 'Scan Inbox'}
                    </button>
                </div>
            </header>

            {/* Stats */}
            <ScoreboardStats days="30" />

            {/* Two-column: workspace + activity */}
            <div className="flex gap-5 items-start flex-wrap">
                <div className="flex-[1.7] min-w-[420px] flex flex-col gap-4">
                    {/* Dropzone (existing component, real upload) */}
                    <UploadZone compact={jobs.length > 0} />

                    <div className="flex items-center gap-2.5 flex-wrap">
                        <div className="font-sans font-bold text-[15px] tracking-tight text-ink-800">Workspace</div>
                        <div className="flex gap-1.5 flex-wrap ml-0.5 text-[12px] font-medium">
                            <span className="px-2.5 py-1 rounded-lg bg-ink-800 text-paper">All {counts.all}</span>
                            <span className="px-2.5 py-1 rounded-lg bg-white border border-stone-200 text-stone-500">Needs you · {counts.needs}</span>
                            <span className="px-2.5 py-1 rounded-lg bg-white border border-stone-200 text-stone-500">Working · {counts.working}</span>
                            <span className="px-2.5 py-1 rounded-lg bg-white border border-stone-200 text-stone-500">Live · {counts.live}</span>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 xl:grid-cols-3 gap-3.5">
                        {jobs.map(job => (
                            <WorkspaceCard key={job.id} job={job} onSelect={setSelectedJob} />
                        ))}
                    </div>
                </div>

                <div className="flex-1 min-w-[296px] sticky top-0">
                    <ActivityRail />
                </div>
            </div>
        </div>
    )
}
