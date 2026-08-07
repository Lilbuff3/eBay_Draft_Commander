import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ReviewQueue } from './ReviewQueue';
import { useCommanderStore } from '@/store/useCommanderStore';
import type { Job } from '@/lib/api';

// Mock matchMedia if needed
if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation(query => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    }));
}

const mockListings: Job[] = [
    {
        id: 'job-1',
        name: 'Vintage Camera',
        display_name: 'Vintage Camera',
        folder_path: 'C:/inbox/camera',
        price: '149.99',
        status: 'pending_review',
        // Real pipeline shape: flat pricing_* keys on ai_data (not nested pricing_data)
        ai_data: {
            pricing_confidence: 'low',
            pricing_confidence_reason: 'Testing confidence reason',
            pricing_comps: [],
            pricing_range: [100, 200],
            pricing_median: 150,
            pricing_comp_count: 5,
            pricing_reasoning: 'Keyword comps',
            pricing_source: 'market_data_keyword',
        },
        confidence_score: 0.75,
        thumbnail_url: '',
        listing_id: null,
        offer_id: null,
        error_type: null,
        error_message: 'Low pricing confidence — Testing confidence reason',
        started_at: null,
        completed_at: null,
    },
    {
        id: 'job-2',
        name: 'Rusty Spanner',
        display_name: 'Rusty Spanner',
        folder_path: 'C:/inbox/spanner',
        price: '19.99',
        status: 'pending_review',
        confidence_score: 0.95,
        thumbnail_url: '',
        listing_id: null,
        offer_id: null,
        error_type: null,
        error_message: null,
        started_at: null,
        completed_at: null,
    },
];

describe('ReviewQueue Component', () => {
    beforeEach(() => {
        useCommanderStore.setState({
            pendingListings: mockListings,
            fetchPending: vi.fn().mockResolvedValue(true),
            approvePending: vi.fn().mockResolvedValue(undefined),
            updatePending: vi.fn().mockResolvedValue(undefined),
            deletePending: vi.fn().mockResolvedValue(undefined),
        });
    });

    it('renders the queue items', async () => {
        render(<ReviewQueue />);

        await waitFor(() => {
            expect(screen.queryByText(/Review and approve listings/)).toBeInTheDocument();
        });

        expect(screen.getByText('Vintage Camera')).toBeInTheDocument();
        expect(screen.getByText('Rusty Spanner')).toBeInTheDocument();
        expect(screen.getByText('$149.99')).toBeInTheDocument();
        expect(screen.getByText('75%')).toBeInTheDocument();
        expect(screen.getByText('95%')).toBeInTheDocument();
    });

    it('renders the price explainer from flat pricing_* ai_data keys', async () => {
        render(<ReviewQueue />);

        await waitFor(() => {
            expect(screen.getByText('Vintage Camera')).toBeInTheDocument();
        });

        // Range bar median from pricing_median
        expect(screen.getAllByText('median $150.00').length).toBeGreaterThan(0);
        // Low-confidence reason banner
        expect(screen.getAllByText('Testing confidence reason').length).toBeGreaterThan(0);
    });
});
