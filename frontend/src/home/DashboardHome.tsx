import { useQuery } from '@tanstack/react-query'
import { PlugZap, ScanLine, Settings as SettingsIcon, ShieldAlert } from 'lucide-react'
import { motion, type Variants } from 'framer-motion'
import { useIsMobile } from '@/hooks/useIsMobile'
import { fetchJobs } from '@/lib/api'
import { getStatusBucket } from '@/lib/status'
import { useCommanderStore } from '@/store/useCommanderStore'
import { UploadZone } from '@/components/UploadZone'
import { ScoreboardStats } from './ScoreboardStats'
import { OrderStats } from './OrderStats'
import { TodayPanel } from './TodayPanel'
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
    // Socket.IO pushes job updates when connected — only poll as a fallback
    const isSocketConnected = useCommanderStore(s => s.isSocketConnected)
    const { data: jobs = [], isPending: jobsPending } = useQuery({ queryKey: ['jobs'], queryFn: fetchJobs, refetchInterval: isSocketConnected ? false : 5000 })

    const setSelectedJob = useCommanderStore(s => s.setSelectedJob)
    const setActiveTab = useCommanderStore(s => s.setActiveTab)
    const handleScan = useCommanderStore(s => s.handleScan)
    const isScanning = useCommanderStore(s => s.isScanning)
    const ebayStatus = useCommanderStore(s => s.ebayStatus)
    const isMobile = useIsMobile()

    const needsReviewCount = jobs.filter(j => j.status === 'pending_review').length

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

    const containerVariants: Variants = {
        hidden: { opacity: 0 },
        show: {
            opacity: 1,
            transition: { staggerChildren: 0.1, delayChildren: 0.05 }
        }
    }

    const itemVariants: Variants = {
        hidden: { opacity: 0, y: 20 },
        show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } }
    }

    return (
        <div className="min-h-screen text-foreground">
            <motion.div 
                className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6"
                variants={containerVariants}
                initial="hidden"
                animate="show"
            >
                
                {/* Header */}
                <motion.header variants={itemVariants} className="flex justify-between items-center pb-2">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-persimmon-600 flex items-center justify-center shadow-sm">
                            <span className="font-bold text-white text-sm">DC</span>
                        </div>
                        <div>
                            <div className="text-xs font-bold tracking-widest text-stone-500 uppercase">Draft Commander</div>
                            <h1 className="font-display font-bold text-2xl tracking-tight leading-none text-ink-800 mt-1">
                                Good {part}, {userName}
                            </h1>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <button
                            onClick={handleScan}
                            disabled={isScanning}
                            className="hidden sm:flex items-center gap-2 h-11 bg-persimmon-50 border border-persimmon-200 hover:bg-persimmon-100 transition-colors rounded-full px-4 disabled:opacity-50 cursor-pointer"
                        >
                            {isScanning ? (
                                <div className="w-4 h-4 rounded-full border-2 border-persimmon-500 border-t-transparent animate-spin mr-1"></div>
                            ) : (
                                <ScanLine className="w-4 h-4 text-persimmon-600" />
                            )}
                            <span className="text-xs font-bold text-persimmon-600">
                                {isScanning ? 'Scanning...' : 'Scan Inbox'}
                            </span>
                        </button>

                        {/* Mobile Settings — also reachable from the More tab. */}
                        <button
                            onClick={() => setActiveTab('settings')}
                            className="flex sm:hidden items-center justify-center w-11 h-11 bg-paper-card border border-stone-200 rounded-xl hover:bg-stone-100 transition-colors cursor-pointer text-stone-600 hover:text-ink-800"
                            aria-label="Settings"
                        >
                            <SettingsIcon className="w-5 h-5" />
                        </button>
                    </div>
                </motion.header>

                {/* eBay token dead = every listing fails. Loud, phone-visible. */}
                {ebayStatus === 'disconnected' && (
                    <motion.div variants={itemVariants}>
                        <button
                            onClick={() => setActiveTab('settings')}
                            className="w-full flex items-center gap-3 rounded-2xl bg-red-50 border border-red-300 px-4 py-3 text-left hover:bg-red-100 transition-colors"
                        >
                            <PlugZap className="w-5 h-5 text-red-600 shrink-0" />
                            <div className="flex-1 min-w-0">
                                <div className="text-sm font-bold text-red-800">eBay disconnected</div>
                                <div className="text-xs text-red-700">New listings will fail — tap to check the token in Settings</div>
                            </div>
                        </button>
                    </motion.div>
                )}

                {/* Price-flagged jobs waiting for a human — tap through to review */}
                {needsReviewCount > 0 && (
                    <motion.div variants={itemVariants}>
                        <button
                            onClick={() => setActiveTab('review')}
                            className="w-full flex items-center gap-3 rounded-2xl bg-clay-300/25 border border-clay-400 px-4 py-3 text-left hover:bg-clay-300/40 transition-colors"
                        >
                            <ShieldAlert className="w-5 h-5 text-clay-600 shrink-0" />
                            <div className="flex-1 min-w-0">
                                <div className="text-sm font-bold text-ink-800">
                                    {needsReviewCount} listing{needsReviewCount !== 1 ? 's' : ''} waiting for price review
                                </div>
                                <div className="text-xs text-ink-500">Approve or fix them before they go live</div>
                            </div>
                        </button>
                    </motion.div>
                )}

                {/* Stats */}
                <motion.div variants={itemVariants}>
                    <ScoreboardStats days="30" />
                </motion.div>

                {/* Orders needing shipment — loud when due, hidden when clear */}
                <motion.div variants={itemVariants}>
                    <OrderStats />
                </motion.div>

                {/* Autopilot daily report + live price-discovery count */}
                <motion.div variants={itemVariants}>
                    <TodayPanel />
                </motion.div>



                {/* Stacked on phones, two columns from md. The old `flex flex-wrap`
                    never wrapped — the workspace column could shrink to zero (min-w-0)
                    while the rail held its 296px floor, so the two overlapped. */}
                <motion.div variants={itemVariants} className="flex flex-col md:flex-row gap-5 items-stretch md:items-start mt-6">
                    <div className="md:flex-[1.7] min-w-0 flex flex-col gap-4">
                        {showWorkspace ? (
                            <>
                                {!isMobile && <UploadZone compact />}

                                <div className="flex items-center gap-2.5 flex-wrap">
                                    <div className="font-sans font-bold text-[15px] tracking-tight text-ink-800">Workspace</div>
                                    <div className="flex gap-1.5 flex-wrap ml-0.5 text-xs font-medium">
                                        {needs > 0 && (
                                            <span className="px-2.5 py-1 rounded-lg bg-red-50 text-red-700 border border-red-200">Needs you · {needs}</span>
                                        )}
                                        {working > 0 && (
                                            <span className="px-2.5 py-1 rounded-lg bg-persimmon-50 text-persimmon-700 border border-persimmon-200">Working · {working}</span>
                                        )}
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                                    {activeJobs.map(job => (
                                        <WorkspaceCard key={job.id} job={job} onSelect={setSelectedJob} />
                                    ))}
                                </div>
                            </>
                        ) : jobsPending ? (
                            /* "All caught up" before the jobs land would be a claim we can't make yet. */
                            <div className="rounded-3xl border border-stone-200 bg-paper-card px-4 py-5 shadow-sm">
                                <div className="h-4 w-2/3 rounded bg-stone-200 animate-pulse" />
                            </div>
                        ) : (
                            <div className="rounded-3xl border border-stone-200 bg-paper-card px-4 py-5 text-sm text-stone-500 flex items-start gap-3 shadow-sm">
                                <span className="text-sage-500 font-bold mt-px text-lg">✓</span>
                                <span>All caught up — nothing needs you. Photos sent over WhatsApp list automatically; they’ll show here only if one needs a hand.</span>
                            </div>
                        )}
                    </div>

                    <div className="w-full md:flex-1 md:min-w-[296px] md:sticky md:top-0">
                        <ActivityRail />
                    </div>
                </motion.div>
            </motion.div>
        </div>
    )
}
