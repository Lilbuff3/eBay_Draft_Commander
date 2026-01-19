import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    LayoutTemplate, Plus,
    Check, X, Star, StarOff, Search, Folder, Trash2
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface TemplateManagerProps {
    onClose: () => void
    onApply?: (template: Template) => void
}

interface Template {
    id: string
    name: string
    category: string
    description?: string
    fields: Record<string, string>
    isDefault: boolean
    isFavorite: boolean
    usageCount: number
}

export function TemplateManager({ onClose, onApply }: TemplateManagerProps) {
    const [templates, setTemplates] = useState<Template[]>([])
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null)

    // Load templates on mount
    useEffect(() => {
        loadTemplates()
    }, [])

    const loadTemplates = async () => {
        try {
            const res = await fetch('/api/tools/templates')
            const data = await res.json()
            setTemplates(data)
        } catch (err) {
            console.error('Failed to load templates:', err)
        }
    }

    const categories = [...new Set(templates.map(t => t.category))]

    const filteredTemplates = templates.filter(t => {
        const matchesSearch = t.name.toLowerCase().includes(searchQuery.toLowerCase())
        const matchesCategory = !selectedCategory || t.category === selectedCategory
        return matchesSearch && matchesCategory
    })

    // --- Actions ---

    const handleCreate = async () => {
        // Quick create for now - Plan to add full editor later
        const name = prompt("Enter template name:")
        if (!name) return

        const category = prompt("Category (e.g. Electronics, Clothing):", "General") || "General"

        const newTemplate: Partial<Template> = {
            name,
            category,
            description: 'New custom template',
            fields: {
                condition: 'Used',
                shipping: 'Calculated'
            },
            isDefault: false,
            isFavorite: false,
            usageCount: 0
        }

        try {
            const res = await fetch('/api/tools/templates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newTemplate)
            })
            const json = await res.json()
            if (json.success) {
                loadTemplates()
            }
        } catch (err) {
            console.error('Failed to create template:', err)
        }
    }

    const handleToggleFavorite = async (t: Template, e: React.MouseEvent) => {
        e.stopPropagation()
        const updated = { ...t, isFavorite: !t.isFavorite }

        // Optimistic update
        setTemplates(prev => prev.map(p => p.id === t.id ? updated : p))

        try {
            await fetch('/api/tools/templates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updated)
            })
        } catch (err) {
            loadTemplates() // Revert on error
        }
    }

    const handleDelete = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation()
        if (!confirm("Are you sure you want to delete this template?")) return

        try {
            await fetch(`/api/tools/templates?id=${id}`, { method: 'DELETE' })
            setTemplates(prev => prev.filter(t => t.id !== id))
        } catch (error) {
            console.error('Failed to delete template:', error)
        }
    }

    const handleApply = async (template: Template) => {
        onApply?.(template)

        // Update usage count silently
        try {
            const updated = { ...template, usageCount: template.usageCount + 1 }
            setTemplates(prev => prev.map(t => t.id === template.id ? updated : t))

            await fetch('/api/tools/templates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updated)
            })
        } catch (e) {
            // Ignore stats errors
        }
    }

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="bg-white rounded-3xl border border-stone-200 shadow-xl overflow-hidden flex flex-col h-[600px]"
        >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-stone-100 bg-gradient-to-r from-purple-50 to-white shrink-0">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-purple-500 flex items-center justify-center text-white shadow-sm">
                        <LayoutTemplate size={20} />
                    </div>
                    <div>
                        <h2 className="font-semibold text-stone-800">Templates</h2>
                        <p className="text-xs text-stone-400">Manage listing presets</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button size="sm" onClick={handleCreate} className="bg-purple-500 hover:bg-purple-600">
                        <Plus size={16} className="mr-1" /> New Template
                    </Button>
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <X size={18} />
                    </Button>
                </div>
            </div>

            <div className="flex flex-1 overflow-hidden">
                {/* Sidebar */}
                <div className="w-56 border-r border-stone-100 p-4 bg-stone-50/50 flex flex-col overflow-y-auto">
                    {/* Search */}
                    <div className="relative mb-4 shrink-0">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" size={16} />
                        <Input
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search..."
                            className="pl-9 text-sm"
                        />
                    </div>

                    {/* Categories */}
                    <div className="space-y-1 shrink-0">
                        <button
                            onClick={() => setSelectedCategory(null)}
                            className={cn(
                                'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition-colors',
                                !selectedCategory
                                    ? 'bg-purple-100 text-purple-700 font-medium'
                                    : 'text-stone-600 hover:bg-stone-100'
                            )}
                        >
                            <Folder size={16} />
                            All Templates
                            <Badge variant="secondary" className="ml-auto">{templates.length}</Badge>
                        </button>

                        {categories.map(cat => {
                            const count = templates.filter(t => t.category === cat).length
                            return (
                                <button
                                    key={cat}
                                    onClick={() => setSelectedCategory(cat)}
                                    className={cn(
                                        'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left transition-colors',
                                        selectedCategory === cat
                                            ? 'bg-purple-100 text-purple-700 font-medium'
                                            : 'text-stone-600 hover:bg-stone-100'
                                    )}
                                >
                                    <Folder size={16} />
                                    {cat}
                                    <Badge variant="secondary" className="ml-auto">{count}</Badge>
                                </button>
                            )
                        })}
                    </div>

                    {/* Favorites Quick Access */}
                    {templates.some(t => t.isFavorite) && (
                        <div className="mt-6 pt-4 border-t border-stone-200 shrink-0">
                            <h4 className="text-xs font-semibold text-stone-400 uppercase tracking-wider mb-2 px-3">
                                Favorites
                            </h4>
                            {templates.filter(t => t.isFavorite).map(t => (
                                <button
                                    key={t.id}
                                    onClick={() => handleApply(t)}
                                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left text-stone-600 hover:bg-stone-100 transition-colors"
                                >
                                    <Star size={14} className="text-amber-500 fill-amber-500" />
                                    <span className="truncate">{t.name}</span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* Template Grid */}
                <div className="flex-1 p-6 overflow-y-auto">
                    <div className="grid grid-cols-2 gap-4">
                        <AnimatePresence>
                            {filteredTemplates.map((template, index) => (
                                <motion.div
                                    key={template.id}
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.95 }}
                                    transition={{ delay: index * 0.05 }}
                                    className={cn(
                                        'group relative p-4 rounded-2xl border transition-all duration-200 cursor-pointer',
                                        template.isDefault
                                            ? 'bg-gradient-to-br from-purple-50 to-white border-purple-200 shadow-sm'
                                            : 'bg-white border-stone-100 hover:border-purple-200 hover:shadow-md'
                                    )}
                                    // Make whole card clickable mainly for selection, 
                                    // but prevent triggering if clicking actions
                                    onClick={() => handleApply(template)}
                                >
                                    {/* Default Badge */}
                                    {template.isDefault && (
                                        <Badge className="absolute -top-2 -right-2 bg-purple-500 text-[10px]">
                                            Default
                                        </Badge>
                                    )}

                                    {/* Actions */}
                                    <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                                        <button
                                            onClick={(e) => handleToggleFavorite(template, e)}
                                            className="p-1.5 rounded-lg bg-white shadow-sm hover:bg-stone-50"
                                            title="Toggle Favorite"
                                        >
                                            {template.isFavorite ? (
                                                <Star size={14} className="text-amber-500 fill-amber-500" />
                                            ) : (
                                                <StarOff size={14} className="text-stone-400" />
                                            )}
                                        </button>
                                        <button
                                            onClick={(e) => handleDelete(template.id, e)}
                                            className="p-1.5 rounded-lg bg-white shadow-sm hover:bg-red-50 text-red-400 hover:text-red-500"
                                            title="Delete Template"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>

                                    {/* Content */}
                                    <div className="flex items-start gap-3">
                                        <div className={cn(
                                            'w-10 h-10 rounded-xl flex items-center justify-center text-white',
                                            template.isDefault ? 'bg-purple-500' : 'bg-stone-300'
                                        )}>
                                            <LayoutTemplate size={18} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <h3 className="font-semibold text-stone-800">{template.name}</h3>
                                            <p className="text-xs text-stone-400 mt-0.5 truncate">
                                                {template.description}
                                            </p>
                                        </div>
                                    </div>

                                    {/* Fields Preview */}
                                    <div className="flex flex-wrap gap-1 mt-3">
                                        {Object.entries(template.fields).slice(0, 3).map(([key, value]) => (
                                            <Badge
                                                key={key}
                                                variant="secondary"
                                                className="text-[10px] capitalize"
                                            >
                                                {value}
                                            </Badge>
                                        ))}
                                    </div>

                                    {/* Footer */}
                                    <div className="flex items-center justify-between mt-4 pt-3 border-t border-stone-100">
                                        <span className="text-[10px] text-stone-400">
                                            Used {template.usageCount} times
                                        </span>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            className="h-6 text-xs text-purple-600 hover:text-purple-700 hover:bg-purple-50"
                                        >
                                            <Check size={12} className="mr-1" /> Apply
                                        </Button>
                                    </div>
                                </motion.div>
                            ))}
                        </AnimatePresence>
                    </div>

                    {/* Empty State */}
                    {filteredTemplates.length === 0 && (
                        <div className="text-center py-12 text-stone-400">
                            <LayoutTemplate size={48} className="mx-auto mb-4 opacity-30" />
                            <p className="text-sm">No templates found</p>
                            <Button size="sm" className="mt-4" variant="outline" onClick={handleCreate}>
                                <Plus size={14} className="mr-1" /> Create Template
                            </Button>
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    )
}
