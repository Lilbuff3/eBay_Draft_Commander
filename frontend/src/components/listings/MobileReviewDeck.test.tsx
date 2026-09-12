import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MobileReviewDeck } from './MobileReviewDeck';
import type { Job } from '@/lib/api';

const mockListings: Job[] = [
    {
        id: 'job-1',
        name: 'Vintage Camera',
        display_name: 'Vintage Camera 35mm Rangefinder',
        folder_path: 'C:/inbox/camera',
        price: '49.99',
        status: 'pending_review',
        confidence_score: 0.88,
        thumbnail_url: 'http://localhost/thumb.jpg',
        listing_id: null,
        offer_id: null,
        error_type: null,
        error_message: null,
        cogs: 10.00,
        note: 'Tested and working, small scratch on base',
        started_at: null,
        completed_at: null,
    },
    {
        id: 'job-2',
        name: 'Antique Clock',
        display_name: 'Antique Brass Desk Clock',
        folder_path: 'C:/inbox/clock',
        price: '89.99',
        status: 'pending_review',
        confidence_score: 0.92,
        thumbnail_url: '',
        listing_id: null,
        offer_id: null,
        error_type: null,
        error_message: null,
        cogs: 20.00,
        started_at: null,
        completed_at: null,
    }
];

describe('MobileReviewDeck Component', () => {
    it('renders the first item in the review deck with seller note, price, and net margin', () => {
        const onApprove = vi.fn().mockResolvedValue(undefined);
        const onUpdate = vi.fn().mockResolvedValue(undefined);
        const onDelete = vi.fn().mockResolvedValue(undefined);

        render(
            <MobileReviewDeck
                listings={mockListings}
                onApprove={onApprove}
                onUpdate={onUpdate}
                onDelete={onDelete}
            />
        );

        expect(screen.getByText('1 of 2')).toBeInTheDocument();
        expect(screen.getByDisplayValue('Vintage Camera 35mm Rangefinder')).toBeInTheDocument();
        expect(screen.getByDisplayValue('49.99')).toBeInTheDocument();
        expect(screen.getByText(/Tested and working/)).toBeInTheDocument();
        expect(screen.getByText(/Expected Net Profit/)).toBeInTheDocument();
    });

    it('approves the current item on 1-tap Approve & List Now button', async () => {
        const onApprove = vi.fn().mockResolvedValue(undefined);
        const onUpdate = vi.fn().mockResolvedValue(undefined);
        const onDelete = vi.fn().mockResolvedValue(undefined);

        render(
            <MobileReviewDeck
                listings={mockListings}
                onApprove={onApprove}
                onUpdate={onUpdate}
                onDelete={onDelete}
            />
        );

        const approveBtn = screen.getByRole('button', { name: /Approve & List Now/i });
        fireEvent.click(approveBtn);

        await waitFor(() => {
            expect(onApprove).toHaveBeenCalledWith(['job-1']);
        });
    });
});
