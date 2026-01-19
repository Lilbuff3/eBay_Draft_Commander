import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
    Eye, Monitor, Smartphone, Tablet,
    RefreshCw, X, ZoomIn, ZoomOut, Check, AlertCircle, LayoutTemplate
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

interface PreviewPanelProps {
    jobId?: string
    onClose: () => void
}

interface ValidationItem {
    status: 'pass' | 'warn' | 'fail'
    label: string
    message?: string
}

interface Template {
    id: string
    name: string
    isDefault: boolean
}

export function PreviewPanel({ jobId, onClose }: PreviewPanelProps) {
    const [device, setDevice] = useState<'desktop' | 'tablet' | 'mobile'>('desktop')
    const [zoom, setZoom] = useState(100)
    const [isLoading, setIsLoading] = useState(false)
    const [htmlContent, setHtmlContent] = useState<string>('')
    const [validation, setValidation] = useState<ValidationItem[]>([])

    // Template State
    const [templates, setTemplates] = useState<Template[]>([])
    const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')

    const deviceWidths = {
        desktop: 800,
        tablet: 768,
        mobile: 375
    }

    // Load Templates on Mount
    useEffect(() => {
        fetch('/api/tools/templates')
            .then(res => res.json())
            .then(data => {
                setTemplates(data)
                // Select default if available
                const def = data.find((t: Template) => t.isDefault)
                if (def) setSelectedTemplateId(def.id)
                else if (data.length > 0) setSelectedTemplateId(data[0].id)
            })
            .catch(err => console.error('Failed to load templates:', err))
    }, [])

    const handleRefresh = async () => {
        setIsLoading(true)
        try {
            const queryFn = new URLSearchParams()
            if (jobId) queryFn.append('jobId', jobId)
            if (selectedTemplateId) queryFn.append('templateId', selectedTemplateId)

            const res = await fetch(`/api/tools/preview?${queryFn.toString()}`)
            const data = await res.json()

            setHtmlContent(data.html || '<div style="text-align:center; padding: 50px; color: #999;">No preview available</div>')
            setValidation(data.validation || [])
        } catch (error) {
            console.error('Failed to load preview:', error)
            setHtmlContent('<div style="text-align:center; padding: 50px; color: red;">Failed to load preview</div>')
        } finally {
            setIsLoading(false)
        }
    }

    // Refresh when job or template changes
    useEffect(() => {
        handleRefresh()
    }, [jobId, selectedTemplateId])

    const passCount = validation.filter(v => v.status === 'pass').length
    const warnCount = validation.filter(v => v.status === 'warn').length
    const failCount = validation.filter(v => v.status === 'fail').length

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="bg-white rounded-3xl border border-stone-200 shadow-xl overflow-hidden flex flex-col h-[80vh]"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-stone-100 bg-gradient-to-r from-orange-50 to-white shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-orange-500 flex items-center justify-center text-white shadow-sm">
                        <Eye size={20} />
                    </div>
                    <div>
                        <h2 className="font-semibold text-stone-800">Listing Preview</h2>
                        <p className="text-xs text-stone-400">View as buyer will see it</p>
                    </div>
                </div>

                {/* Template Selector */}
                <div className="flex items-center gap-2 bg-white rounded-lg border border-stone-200 px-3 py-1.5 shadow-sm">
                    <LayoutTemplate size={14} className="text-stone-400" />
                    <select
                        className="text-sm border-none bg-transparent outline-none text-stone-700 font-medium min-w-[150px]"
                        value={selectedTemplateId}
                        onChange={(e) => setSelectedTemplateId(e.target.value)}
                    >
                        <option value="">Select Template...</option>
                        {templates.map(t => (
                            <option key={t.id} value={t.id}>{t.name} {t.isDefault ? '(Default)' : ''}</option>
                        ))}
                    </select>
                </div>

                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isLoading}>
                        <RefreshCw size={14} className={cn("mr-1", isLoading && "animate-spin")} />
                        Refresh
                    </Button>
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <X size={18} />
                    </Button>
                </div>
            </div>

            <div className="flex flex-1 overflow-hidden">
                {/* Preview Area */}
                <div className="flex-1 p-6 bg-stone-50 overflow-y-auto flex flex-col">
                    {/* Device Selector */}
                    <div className="flex items-center justify-between mb-4 shrink-0">
                        <Tabs value={device} onValueChange={(v) => setDevice(v as typeof device)}>
                            <TabsList>
                                <TabsTrigger value="desktop" className="flex items-center gap-1.5">
                                    <Monitor size={14} /> Desktop
                                </TabsTrigger>
                                <TabsTrigger value="tablet" className="flex items-center gap-1.5">
                                    <Tablet size={14} /> Tablet
                                </TabsTrigger>
                                <TabsTrigger value="mobile" className="flex items-center gap-1.5">
                                    <Smartphone size={14} /> Mobile
                                </TabsTrigger>
                            </TabsList>
                        </Tabs>

                        <div className="flex items-center gap-1 bg-white rounded-lg p-1 shadow-sm border border-stone-100">
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={() => setZoom(prev => Math.max(50, prev - 10))}
                            >
                                <ZoomOut size={14} />
                            </Button>
                            <span className="text-xs font-medium text-stone-600 w-12 text-center">{zoom}%</span>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={() => setZoom(prev => Math.min(150, prev + 10))}
                            >
                                <ZoomIn size={14} />
                            </Button>
                        </div>
                    </div>

                    {/* Preview Frame */}
                    <div className="flex justify-center flex-1 min-h-0">
                        <div className="relative w-full flex justify-center overflow-auto">
                            <motion.div
                                animate={{ width: deviceWidths[device] * (zoom / 100) }}
                                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                                className="bg-white rounded-xl shadow-lg border border-stone-200 overflow-hidden origin-top"
                                style={{
                                    height: 'fit-content',
                                    minHeight: '600px',
                                    transform: `scale(${zoom / 100})`, // Wait, scaling layout vs zooming content
                                    // Scaling content directly is better for "Zoom"
                                    // But resizing width is better for "Device"
                                    // Let's rely on width for device, and maybe ignore CSS zoom for now to keep it simple layout-wise,
                                    // Or use container valid
                                }}
                            >
                                {/* Browser Chrome */}
                                <div className="bg-stone-100 px-3 py-2 flex items-center gap-2 border-b border-stone-200">
                                    <div className="flex gap-1.5">
                                        <div className="w-3 h-3 rounded-full bg-red-400" />
                                        <div className="w-3 h-3 rounded-full bg-amber-400" />
                                        <div className="w-3 h-3 rounded-full bg-emerald-400" />
                                    </div>
                                    <div className="flex-1 bg-white rounded px-3 py-1 text-xs text-stone-400 truncate">
                                        ebay.com/itm/preview...
                                    </div>
                                </div>

                                {/* Content */}
                                <div
                                    className="p-4"
                                    dangerouslySetInnerHTML={{ __html: htmlContent }}
                                />
                            </motion.div>
                        </div>
                    </div>
                </div>

                {/* Validation Sidebar */}
                <div className="w-72 border-l border-stone-100 p-6 overflow-y-auto bg-white shrink-0">
                    <h3 className="font-semibold text-stone-800 mb-4">Listing Quality</h3>

                    {/* Summary */}
                    <div className="flex gap-2 mb-6">
                        <div className="flex-1 bg-emerald-50 rounded-xl p-3 text-center">
                            <div className="text-xl font-bold text-emerald-600">{passCount}</div>
                            <div className="text-[10px] text-emerald-600 uppercase tracking-wider">Passed</div>
                        </div>
                        <div className="flex-1 bg-amber-50 rounded-xl p-3 text-center">
                            <div className="text-xl font-bold text-amber-600">{warnCount}</div>
                            <div className="text-[10px] text-amber-600 uppercase tracking-wider">Warn</div>
                        </div>
                        <div className="flex-1 bg-red-50 rounded-xl p-3 text-center">
                            <div className="text-xl font-bold text-red-600">{failCount}</div>
                            <div className="text-[10px] text-red-600 uppercase tracking-wider">Fail</div>
                        </div>
                    </div>

                    {/* Validation Items */}
                    <div className="space-y-2">
                        {validation.map((item, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: index * 0.05 }}
                                className={cn(
                                    'p-3 rounded-xl border',
                                    item.status === 'pass' && 'bg-emerald-50/50 border-emerald-100',
                                    item.status === 'warn' && 'bg-amber-50/50 border-amber-100',
                                    item.status === 'fail' && 'bg-red-50/50 border-red-100'
                                )}
                            >
                                <div className="flex items-center gap-2">
                                    {item.status === 'pass' && <Check size={14} className="text-emerald-500" />}
                                    {item.status === 'warn' && <AlertCircle size={14} className="text-amber-500" />}
                                    {item.status === 'fail' && <X size={14} className="text-red-500" />}
                                    <span className="font-medium text-sm text-stone-700">{item.label}</span>
                                </div>
                                {item.message && (
                                    <p className="text-xs text-stone-500 mt-1 ml-6">{item.message}</p>
                                )}
                            </motion.div>
                        ))}
                    </div>
                </div>
            </div>
        </motion.div>
    )
}
