import { useState, useEffect } from 'react'
import { ChevronDown, Truck, Check, Loader2 } from 'lucide-react'

interface ShippingPolicy {
    id: string
    name: string
    description: string
}

interface ShippingSelectorProps {
    value?: string
    onChange?: (policyId: string) => void
    className?: string
}

export function ShippingSelector({ value, onChange, className = '' }: ShippingSelectorProps) {
    const [policies, setPolicies] = useState<ShippingPolicy[]>([])
    const [defaultPolicy, setDefaultPolicy] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    const [isOpen, setIsOpen] = useState(false)
    const [selected, setSelected] = useState<string | null>(value || null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const fetchPolicies = async () => {
            try {
                const response = await fetch('/api/policies/fulfillment')
                if (!response.ok) throw new Error('Failed to fetch policies')

                const data = await response.json()
                setPolicies(data.policies || [])
                setDefaultPolicy(data.default || null)

                // Set initial selection
                if (!selected && data.default) {
                    setSelected(data.default)
                }
            } catch (err) {
                console.error('Error fetching shipping policies:', err)
                setError('Could not load shipping options')
            } finally {
                setIsLoading(false)
            }
        }

        fetchPolicies()
    }, [])

    const handleSelect = (policyId: string) => {
        setSelected(policyId)
        setIsOpen(false)
        onChange?.(policyId)
    }

    const selectedPolicy = policies.find(p => p.id === selected)

    if (isLoading) {
        return (
            <div className={`flex items-center gap-2 p-3 bg-stone-50 rounded-lg border border-stone-200 ${className}`}>
                <Loader2 size={16} className="animate-spin text-stone-400" />
                <span className="text-sm text-stone-400">Loading shipping options...</span>
            </div>
        )
    }

    if (error) {
        return (
            <div className={`flex items-center gap-2 p-3 bg-red-50 rounded-lg border border-red-200 ${className}`}>
                <Truck size={16} className="text-red-400" />
                <span className="text-sm text-red-500">{error}</span>
            </div>
        )
    }

    return (
        <div className={`relative ${className}`}>
            {/* Dropdown Button */}
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center justify-between gap-2 p-3 bg-stone-50 rounded-lg border border-stone-200 hover:border-stone-300 transition-colors text-left"
            >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                    <Truck size={16} className="text-stone-500 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-stone-800 truncate">
                            {selectedPolicy?.name || 'Select Shipping'}
                        </div>
                        {selectedPolicy && (
                            <div className="text-xs text-stone-400 truncate">
                                {selectedPolicy.description}
                            </div>
                        )}
                    </div>
                </div>
                <ChevronDown
                    size={16}
                    className={`text-stone-400 flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                />
            </button>

            {/* Dropdown Menu */}
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 z-10"
                        onClick={() => setIsOpen(false)}
                    />

                    {/* Menu */}
                    <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-lg border border-stone-200 shadow-lg z-20 max-h-64 overflow-y-auto">
                        {policies.map(policy => (
                            <button
                                key={policy.id}
                                onClick={() => handleSelect(policy.id)}
                                className={`w-full flex items-center gap-3 p-3 text-left hover:bg-stone-50 transition-colors ${policy.id === selected ? 'bg-blue-50' : ''
                                    }`}
                            >
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm font-medium text-stone-800">
                                            {policy.name}
                                        </span>
                                        {policy.id === defaultPolicy && (
                                            <span className="text-[10px] px-1.5 py-0.5 bg-stone-100 text-stone-500 rounded uppercase">
                                                Default
                                            </span>
                                        )}
                                    </div>
                                    <div className="text-xs text-stone-400 truncate">
                                        {policy.description}
                                    </div>
                                </div>
                                {policy.id === selected && (
                                    <Check size={16} className="text-blue-500 flex-shrink-0" />
                                )}
                            </button>
                        ))}

                        {policies.length === 0 && (
                            <div className="p-4 text-center text-sm text-stone-400">
                                No shipping policies found
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    )
}
