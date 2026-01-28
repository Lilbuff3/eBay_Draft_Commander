import { useEffect, useRef } from 'react';
import { toast } from 'sonner';

interface BookData {
    title: string;
    item_specifics: any;
    description: string;
    category_id: string;
    price: number;
    stock_photo: string;
}

interface ScannerListenerProps {
    onScan: (data: BookData) => void;
    isScanning: boolean;
}

export function ScannerListener({ onScan }: Omit<ScannerListenerProps, 'isScanning'>) {
    const bufferRef = useRef<string>('');
    const lastKeystrokeRef = useRef<number>(0);

    useEffect(() => {
        const handleKeyDown = async (e: KeyboardEvent) => {
            // Ignore if user is typing in an input field
            const target = e.target as HTMLElement;
            if (['INPUT', 'TEXTAREA'].includes(target.tagName) || target.isContentEditable) {
                return;
            }

            const now = Date.now();

            // Reset buffer if too much time passed (manual typing vs scanner rapid input)
            // Scanners typically type very fast (<20ms per char)
            if (now - lastKeystrokeRef.current > 50) {
                bufferRef.current = '';
            }
            lastKeystrokeRef.current = now;

            if (e.key === 'Enter') {
                const currentBuffer = bufferRef.current;
                // ISBNs are 10 or 13 digits
                if (currentBuffer.length >= 10 && /^\d+$/.test(currentBuffer)) {
                    console.log("Scanner Input Detected:", currentBuffer);
                    await lookupISBN(currentBuffer);
                }
                bufferRef.current = '';
            } else if (e.key.length === 1) {
                bufferRef.current += e.key;
            }
        };

        const lookupISBN = async (isbn: string) => {
            try {
                const toastId = toast.loading(`Looking up Book: ${isbn}...`);

                const res = await fetch(`http://localhost:5000/api/lookup/book?isbn=${isbn}`);
                const data = await res.json();

                toast.dismiss(toastId);

                if (data.success) {
                    toast.success("Book Found!", { description: data.title });
                    onScan(data);
                } else {
                    toast.error("Book not found in catalog", { description: `ISBN: ${isbn}` });
                }
            } catch (err) {
                toast.dismiss();
                toast.error("Network Error: Could not lookup book");
                console.error(err);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [onScan]);

    return null;
}
