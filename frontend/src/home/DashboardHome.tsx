import { useQuery } from '@tanstack/react-query'
import { ScanLine } from 'lucide-react'
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


    // Capture-and-forget: the money strip (ScoreboardStats) is the home. The
    // workspace below it only appears when something actually needs eyes —
    // a job mid-flight (working) or one that errored (needs_you). Completed/live
    // items live in Inventory, not here, so the home stays a clean money view.
    const activeJobs = jobs.filter(j => {
        const b = getStatusBucket(j.status)
        return b === 'working' || b === 'needs_you'
    })
    const needs = activeJobs.filter(j => getStatusBucket(j.status) === 'needs_you').length
    const working = activeJobs.filter(j => getStatusBucket(j.status) === 'working').length
    const showWorkspace = activeJobs.length > 0

    return (
        <div className="dark bg-slate-950 text-slate-100 min-h-screen">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6">
                
                {/* Header */}
                <header className="flex justify-between items-center pb-2">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center shadow-glow">
                            <span className="font-bold text-white text-sm">DC</span>
                        </div>
                        <div>
                            <div className="text-[10px] font-bold tracking-widest text-slate-400 uppercase">Draft Commander</div>
                            <h1 className="font-display font-bold text-2xl tracking-tight leading-none text-white mt-1">
                                Good {part}, {userName}
                            </h1>
                        </div>
                    </div>
                    
                    <div className="flex items-center gap-4">
                        <button
                            onClick={handleScan}
                            disabled={isScanning}
                            className="hidden sm:flex items-center gap-2 bg-brand-500/20 border border-brand-500/50 hover:bg-brand-500/30 transition-colors rounded-full px-4 py-1.5 shadow-[0_0_15px_rgba(167,139,250,0.15)] disabled:opacity-50 cursor-pointer"
                        >
                            {isScanning ? (
                                <div className="w-4 h-4 rounded-full border-2 border-brand-400 border-t-transparent animate-spin mr-1"></div>
                            ) : (
                                <ScanLine className="w-4 h-4 text-brand-400" />
                            )}
                            <span className="text-xs font-bold text-brand-400">
                                {isScanning ? 'Scanning...' : 'Scan Inbox'}
                            </span>
                        </button>
                    </div>
                </header>

                {/* Stats */}
                <ScoreboardStats days="30" />



                {/* Two-column: workspace + activity */}
                <div className="flex gap-5 items-start flex-wrap mt-6">
                    <div className="flex-[1.7] min-w-[420px] flex flex-col gap-4">
                        {showWorkspace ? (
                            <>
                                <UploadZone compact />

                                <div className="flex items-center gap-2.5 flex-wrap">
                                    <div className="font-sans font-bold text-[15px] tracking-tight text-white">Workspace</div>
                                    <div className="flex gap-1.5 flex-wrap ml-0.5 text-[12px] font-medium">
                                        {needs > 0 && (
                                            <span className="px-2.5 py-1 rounded-lg bg-red-500/20 text-red-300 border border-red-500/30">Needs you · {needs}</span>
                                        )}
                                        {working > 0 && (
                                            <span className="px-2.5 py-1 rounded-lg bg-brand-500/20 text-brand-300 border border-brand-500/30">Working · {working}</span>
                                        )}
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                                    {activeJobs.map(job => (
                                        <WorkspaceCard key={job.id} job={job} onSelect={setSelectedJob} />
                                    ))}
                                </div>
                            </>
                        ) : (
                            <div className="rounded-3xl border border-slate-700/50 bg-slate-900/40 backdrop-blur-xl px-4 py-5 text-[13px] text-slate-400 flex items-start gap-3 shadow-lg">
                                <span className="text-brand-400 font-bold mt-px text-lg">✓</span>
                                <span>All caught up — nothing needs you. Photos sent over WhatsApp list automatically; they’ll show here only if one needs a hand.</span>
                            </div>
                        )}
                    </div>

                    <div className="flex-1 min-w-[296px] sticky top-0">
                        <ActivityRail />
                    </div>
                </div>
            </div>
        </div>
    )
}
