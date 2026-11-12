import { abortError, failureCode, failureFacts } from './failures.js';

// Two bounded passes: the second revisits failures after neighbouring work may
// have opened a path or provided support. Never keep fighting repeated failures.
export async function runBlockBatch(cells, action, { signal, deadline, reserveMs = 15000 } = {}) {
    const results = new Map();
    let todo = cells.map((cell, index) => ({ cell, index }));
    let failuresInRow = 0, stopped = null;
    const retryable = new Set(['no_support', 'no_stand_spot', 'no_path', 'approach_failed', 'out_of_reach', 'occluded', 'not_visible_or_range', 'placement_unconfirmed', 'action_failed', 'unknown']);
    for (let pass = 0; pass < 2 && todo.length && !stopped; pass++) {
        const next = [];
        for (let i = 0; i < todo.length; i++) {
            const item = todo[i];
            if (signal?.aborted) throw signal.reason ?? abortError('Batch cancelled');
            if (Number.isFinite(deadline) && Date.now() >= deadline - reserveMs) {
                stopped = 'time_limit';
                next.push(...todo.slice(i));
                break;
            }
            try {
                const result = await action(item.cell);
                results.set(item.index, { at: item.cell, status: result?.alreadyPresent ? 'already_done' : 'done', ...result });
                failuresInRow = 0;
            } catch (error) {
                if (signal?.aborted || error?.name === 'AbortError') throw error;
                const code = failureCode(error);
                results.set(item.index, { at: item.cell, status: 'failed', code, reason: String(error?.message ?? error).slice(0, 220), ...(failureFacts.get(error)?.next ? { next: failureFacts.get(error).next } : {}) });
                if (pass === 0 && retryable.has(code)) next.push(item);
                failuresInRow++;
                if (code === 'missing_item' || failuresInRow >= 3) {
                    stopped = code === 'missing_item' ? 'missing_item' : 'three_failures_in_a_row';
                    next.push(...todo.slice(i + 1));
                    break;
                }
            }
        }
        todo = next;
    }
    const entries = cells.map((cell, index) => results.get(index) ?? { at: cell, status: 'not_attempted' });
    return {
        requested: cells.length,
        completed: entries.filter(e => e.status === 'done').length,
        alreadyDone: entries.filter(e => e.status === 'already_done').length,
        failed: entries.filter(e => e.status === 'failed'),
        notAttempted: entries.filter(e => e.status === 'not_attempted').map(e => e.at),
        completedCells: entries.filter(e => e.status === 'done').map(e => e.at),
        ...(stopped ? { stopped, next: 'Stop repeating this batch. Inspect the cause and do another useful task before trying again.' } : {}),
    };
}
