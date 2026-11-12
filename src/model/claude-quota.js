import { mkdir, writeFile, rename } from 'node:fs/promises';
import path from 'node:path';

// Claude Code's stream-json events may expose either unified windows or a
// single warning window. Missing fields are never treated as zero usage.
export function extractClaudeQuota(event) {
    if (event?.type !== 'rate_limit_event' || !event.rate_limit_info) return null;
    const info = event.rate_limit_info;
    const windows = {};
    for (const name of ['five_hour', 'seven_day']) {
        const entry = info.unifiedWindows?.[name] ?? (info.rateLimitType === name ? info : null);
        if (!entry || typeof entry.utilization !== 'number' || entry.utilization < 0 || entry.utilization > 1) continue;
        windows[name] = { usedPercent: entry.utilization * 100, resetsAt: typeof entry.resetsAt === 'number' ? entry.resetsAt : null };
    }
    return Object.keys(windows).length ? { checkedAt: new Date().toISOString(), windows } : null;
}

export async function saveClaudeQuota(file, quota) {
    await mkdir(path.dirname(file), { recursive: true });
    const temp = `${file}.${process.pid}.tmp`;
    await writeFile(temp, JSON.stringify(quota), { mode: 0o600 });
    await rename(temp, file);
}
