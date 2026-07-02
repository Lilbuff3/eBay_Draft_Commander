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
                        <div className="hidden sm:flex items-center bg-brand-500/20 border border-brand-500/50 rounded-full px-4 py-1.5 shadow-[0_0_15px_rgba(167,139,250,0.15)]">
                            <div className="w-2 h-2 rounded-full bg-brand-400 animate-pulse mr-2"></div>
                            <span className="text-xs font-bold text-brand-400">AI online</span>
                        </div>
                    </div>
                </header>

                {/* Stats */}
                <ScoreboardStats days="30" />

                {/* AI Scan Section */}
                <section className="mt-2">
                    <h2 className="text-sm font-semibold text-slate-300 mb-3 px-1">AI Scan</h2>
                    <div className="bg-slate-900/30 backdrop-blur-2xl border border-slate-700/50 rounded-3xl p-3 relative shadow-lg max-w-2xl">
                        {/* Image container */}
                        <div className="relative w-full h-[250px] rounded-2xl overflow-hidden bg-slate-800">
                            {/* We use a placeholder here for the AI scan hero, simulating the Romaleos 4 */}
                            <img src="https://images.unsplash.com/photo-1542291026-7eec264c27ff?q=80&w=1200&auto=format&fit=crop" alt="Shoe Scan" className="w-full h-full object-cover hue-rotate-[240deg] contrast-125" />
                            
                            {/* Bounding Boxes */}
                            <div className="absolute border border-brand-400 bg-brand-500/20 rounded-md top-[35%] left-[10%] w-[55%] h-[40%] shadow-[0_0_15px_rgba(167,139,250,0.3)]">
                                <span className="absolute -top-6 left-1/2 -translate-x-1/2 bg-slate-900 border border-brand-500 text-[10px] px-2 py-0.5 rounded-full text-white font-medium whitespace-nowrap shadow-glow">Swoosh</span>
                            </div>
                            <div className="absolute border border-brand-400 bg-brand-500/20 rounded-md top-[20%] right-[25%] w-[15%] h-[20%] shadow-[0_0_10px_rgba(167,139,250,0.2)]">
                                <span className="absolute -top-6 left-1/2 -translate-x-1/2 bg-slate-900 border border-brand-500 text-[10px] px-2 py-0.5 rounded-full text-white font-medium whitespace-nowrap shadow-glow">Tag</span>
                            </div>
                            <div className="absolute border border-brand-400 bg-brand-500/20 rounded-md bottom-[10%] left-[20%] w-[45%] h-[15%] shadow-[0_0_10px_rgba(167,139,250,0.2)]">
                                <span className="absolute -bottom-6 left-1/2 -translate-x-1/2 bg-slate-900 border border-brand-500 text-[10px] px-2 py-0.5 rounded-full text-white font-medium whitespace-nowrap shadow-glow">Sole</span>
                            </div>
                        </div>

                        {/* Glowing Match Button Overlapping */}
                        <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 cursor-pointer hover:scale-105 transition-transform z-10" onClick={handleScan}>
                            <div className="bg-slate-900 border border-brand-500 px-6 py-2.5 rounded-full flex items-center gap-2 shadow-glow">
                                <ScanLine className="w-5 h-5 text-brand-400" />
                                <span className="text-[14px] font-bold text-white tracking-wide">{isScanning ? 'Scanning...' : 'Scan Inbox'}</span>
                            </div>
                        </div>
                    </div>
                </section>

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
