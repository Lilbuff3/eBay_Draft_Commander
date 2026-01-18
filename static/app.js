/**
 * eBay Draft Commander - Mobile Web Control JavaScript
 */

// State
let currentStatus = 'idle';
let isPaused = false;
let updateInterval = null;

// DOM Elements
const statusIcon = document.getElementById('status-icon');
const statusText = document.getElementById('status-text');
const progressFill = document.getElementById('progress-fill');
const progressCurrent = document.getElementById('progress-current');
const progressTotal = document.getElementById('progress-total');
const progressPercent = document.getElementById('progress-percent');
const currentJobEl = document.getElementById('current-job');
const jobsList = document.getElementById('jobs-list');
const statPending = document.getElementById('stat-pending');
const statCompleted = document.getElementById('stat-completed');
const statFailed = document.getElementById('stat-failed');
const lastUpdate = document.getElementById('last-update');
const btnStart = document.getElementById('btn-start');
const btnPause = document.getElementById('btn-pause');

// Status icons and text mapping
const STATUS_CONFIG = {
    'idle': { icon: '💤', text: 'Idle', class: 'idle' },
    'ready': { icon: '📋', text: 'Ready', class: 'ready' },
    'processing': { icon: '⚙️', text: 'Processing', class: 'processing' },
    'paused': { icon: '⏸️', text: 'Paused', class: 'paused' },
    'error': { icon: '❌', text: 'Error', class: 'error' }
};

const JOB_STATUS_ICONS = {
    'pending': '⏳',
    'processing': '⚙️',
    'completed': '✅',
    'failed': '❌',
    'paused': '⏸️',
    'skipped': '⏭️'
};

/**
 * Initialize the app
 */
function init() {
    // Start auto-refresh
    refresh();
    startAutoRefresh();

    // Add pull-to-refresh for mobile
    let touchStartY = 0;
    document.addEventListener('touchstart', e => {
        touchStartY = e.touches[0].clientY;
    });

    document.addEventListener('touchend', e => {
        const touchEndY = e.changedTouches[0].clientY;
        const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;

        if (scrollTop === 0 && touchEndY - touchStartY > 100) {
            refresh();
            showToast('Refreshed');
        }
    });
}

/**
 * Start auto-refresh interval
 */
function startAutoRefresh() {
    if (updateInterval) clearInterval(updateInterval);
    updateInterval = setInterval(refresh, 2000);
}

/**
 * Refresh all data from server
 */
async function refresh() {
    try {
        await Promise.all([
            fetchStatus(),
            fetchJobs()
        ]);
        updateLastRefresh();
    } catch (error) {
        console.error('Refresh error:', error);
    }
}

/**
 * Fetch and update status
 */
async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        currentStatus = data.status;
        isPaused = data.status === 'paused';

        // Update status display
        const config = STATUS_CONFIG[data.status] || STATUS_CONFIG.idle;
        statusIcon.textContent = config.icon;
        statusText.textContent = config.text;
        statusText.className = 'status-text ' + config.class;

        // Add processing animation
        document.querySelector('.status-indicator').classList.toggle('processing',
            data.status === 'processing');

        // Update progress
        progressFill.style.width = data.progress.percent + '%';
        progressCurrent.textContent = data.progress.current;
        progressTotal.textContent = data.progress.total;
        progressPercent.textContent = data.progress.percent;

        // Update stats
        statPending.textContent = data.stats.pending;
        statCompleted.textContent = data.stats.completed;
        statFailed.textContent = data.stats.failed;

        // Update current job
        if (data.current_job) {
            currentJobEl.innerHTML = `Processing: <span class="job-name">${data.current_job.name}</span>`;
        } else {
            currentJobEl.innerHTML = '';
        }

        // Update button states
        updateButtons();

    } catch (error) {
        console.error('Status fetch error:', error);
    }
}

/**
 * Fetch and update jobs list
 */
async function fetchJobs() {
    try {
        const response = await fetch('/api/jobs');
        const jobs = await response.json();

        if (jobs.length === 0) {
            jobsList.innerHTML = '<div class="empty-state">No items in queue<br>Add folders to inbox</div>';
            return;
        }

        // Sort: processing first, then pending, then completed/failed
        const order = { processing: 0, pending: 1, paused: 2, completed: 3, failed: 4, skipped: 5 };
        jobs.sort((a, b) => (order[a.status] || 99) - (order[b.status] || 99));

        let html = '';
        for (const job of jobs) {
            const icon = JOB_STATUS_ICONS[job.status] || '❓';
            let detail = '';
            let priceHtml = '';

            if (job.status === 'completed' && job.listing_id) {
                detail = `Listed: ${job.listing_id.substring(0, 8)}...`;
                if (job.price) {
                    priceHtml = `<span class="job-price">$${job.price}</span>`;
                }
            } else if (job.status === 'failed' && job.error_type) {
                detail = `<span class="error">${job.error_type}</span>`;
            } else if (job.status === 'processing') {
                detail = 'Working...';
            }

            html += `
                <div class="job-item">
                    <span class="job-icon">${icon}</span>
                    <div class="job-info">
                        <div class="job-name">${escapeHtml(job.name)}</div>
                        ${detail ? `<div class="job-detail">${detail}</div>` : ''}
                    </div>
                    ${priceHtml}
                </div>
            `;
        }

        jobsList.innerHTML = html;

    } catch (error) {
        console.error('Jobs fetch error:', error);
        jobsList.innerHTML = '<div class="loading">Error loading jobs</div>';
    }
}

/**
 * Update button states based on current status
 */
function updateButtons() {
    // Start button
    if (currentStatus === 'processing') {
        btnStart.disabled = true;
        btnStart.innerHTML = '▶️ Running';
    } else {
        btnStart.disabled = false;
        btnStart.innerHTML = '▶️ Start';
    }

    // Pause/Resume button
    if (isPaused) {
        btnPause.innerHTML = '▶️ Resume';
        btnPause.classList.remove('btn-warning');
        btnPause.classList.add('btn-primary');
    } else {
        btnPause.innerHTML = '⏸️ Pause';
        btnPause.classList.remove('btn-primary');
        btnPause.classList.add('btn-warning');
    }

    btnPause.disabled = currentStatus !== 'processing' && currentStatus !== 'paused';
}

/**
 * Update last refresh timestamp
 */
function updateLastRefresh() {
    const now = new Date();
    lastUpdate.textContent = now.toLocaleTimeString();
}

/**
 * Start queue processing
 */
async function startQueue() {
    try {
        btnStart.disabled = true;
        const response = await fetch('/api/start', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('Queue started');
            refresh();
        } else {
            showToast(data.error || 'Failed to start', true);
        }
    } catch (error) {
        showToast('Connection error', true);
    }
}

/**
 * Toggle pause/resume
 */
async function togglePause() {
    try {
        btnPause.disabled = true;
        const endpoint = isPaused ? '/api/resume' : '/api/pause';
        const response = await fetch(endpoint, { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast(isPaused ? 'Resumed' : 'Paused');
            refresh();
        } else {
            showToast(data.error || 'Failed', true);
        }
    } catch (error) {
        showToast('Connection error', true);
    }
}

/**
 * Retry failed jobs
 */
async function retryFailed() {
    try {
        const response = await fetch('/api/retry', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast(`Retrying ${data.retried} jobs`);
            refresh();
        } else {
            showToast(data.error || 'Failed to retry', true);
        }
    } catch (error) {
        showToast('Connection error', true);
    }
}

/**
 * Clear completed jobs
 */
async function clearCompleted() {
    try {
        const response = await fetch('/api/clear', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('Cleared completed');
            refresh();
        } else {
            showToast(data.error || 'Failed to clear', true);
        }
    } catch (error) {
        showToast('Connection error', true);
    }
}

/**
 * Show toast notification
 */
function showToast(message, isError = false) {
    // Remove existing toast
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    // Create new toast
    const toast = document.createElement('div');
    toast.className = 'toast' + (isError ? ' error' : '');
    toast.textContent = message;
    document.body.appendChild(toast);

    // Show toast
    setTimeout(() => toast.classList.add('show'), 10);

    // Hide and remove
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize on load
document.addEventListener('DOMContentLoaded', init);
