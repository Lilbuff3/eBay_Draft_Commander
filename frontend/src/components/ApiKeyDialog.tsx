import { useEffect, useRef, useState } from 'react'
import { KeyRound } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { setApiKeyRequestHandler } from '@/lib/api'

/**
 * In-app replacement for the old window.prompt() API-key flow. Mounted once in
 * App; api.ts calls the registered handler on the first 401 and every
 * concurrent 401 awaits the same promise (single-flight), so remote (Tailscale)
 * re-auth is one dialog instead of a stack of native prompts.
 */
export function ApiKeyDialog() {
    const [open, setOpen] = useState(false)
    const [value, setValue] = useState('')
    const resolverRef = useRef<((key: string | null) => void) | null>(null)

    useEffect(() => {
        setApiKeyRequestHandler(() => new Promise<string | null>(resolve => {
            resolverRef.current = resolve
            setOpen(true)
        }))
        return () => setApiKeyRequestHandler(null)
    }, [])

    const finish = (key: string | null) => {
        setOpen(false)
        setValue('')
        resolverRef.current?.(key)
        resolverRef.current = null
    }

    return (
        <Dialog open={open} onOpenChange={(o) => { if (!o) finish(null) }}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <KeyRound size={18} /> Access key required
                    </DialogTitle>
                    <DialogDescription>
                        Enter the API access token from Settings → Security on the server machine.
                    </DialogDescription>
                </DialogHeader>
                <form
                    onSubmit={e => { e.preventDefault(); finish(value.trim() || null) }}
                    className="space-y-3"
                >
                    <Input
                        autoFocus
                        type="password"
                        autoComplete="off"
                        placeholder="API access token"
                        value={value}
                        onChange={e => setValue(e.target.value)}
                    />
                    <div className="flex justify-end gap-2">
                        <Button type="button" variant="outline" onClick={() => finish(null)}>Cancel</Button>
                        <Button type="submit" disabled={!value.trim()}>Connect</Button>
                    </div>
                </form>
            </DialogContent>
        </Dialog>
    )
}
