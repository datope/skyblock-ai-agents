import { DatabaseSync } from 'node:sqlite';
import { setTimeout as sleep } from 'node:timers/promises';

// One public line every four seconds across the team, at most one per player
// every ten seconds. The database makes reservations atomic across processes.
export class ChatPacer {
    constructor(file) {
        this.timers = new Set();
        this.db = new DatabaseSync(file);
        this.db.exec('PRAGMA busy_timeout = 5000; CREATE TABLE IF NOT EXISTS chat_pacing (name TEXT PRIMARY KEY, last_at INTEGER NOT NULL);');
    }
    reserve(name, now = Date.now()) {
        this.db.exec('BEGIN IMMEDIATE');
        try {
            const row = this.db.prepare('SELECT MAX(last_at) AS last_at FROM chat_pacing').get();
            const own = this.db.prepare('SELECT last_at FROM chat_pacing WHERE name=?').get(name);
            const slot = Math.max(now, (row?.last_at ?? 0) + 4000, (own?.last_at ?? 0) + 10000);
            // Avoid trapping the agent in a long speech queue; it can do other work.
            if (slot - now > 10000) { this.db.exec('ROLLBACK'); return null; }
            this.db.prepare('INSERT INTO chat_pacing(name,last_at) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET last_at=excluded.last_at').run(name,slot);
            this.db.exec('COMMIT');
            return slot;
        } catch (e) { try { this.db.exec('ROLLBACK'); } catch {} throw e; }
    }
    async wait(name, signal) {
        const at = this.reserve(name);
        if (at === null) throw new Error('Chat is busy. Keep working and speak later if it is still useful.');
        const delay = Math.max(0,at-Date.now());
        if (delay) await sleep(delay, undefined, { signal });
        return delay;
    }
    schedule(name, send) {
        const at = this.reserve(name);
        if (at === null) return null;
        const delay = Math.max(0, at - Date.now());
        const timer = setTimeout(() => {
            this.timers.delete(timer);
            try { send(); } catch (error) { console.error('Queued chat failed:', error.message); }
        }, delay);
        this.timers.add(timer);
        return delay;
    }
    close() {
        for (const timer of this.timers) clearTimeout(timer);
        this.timers.clear();
        this.db.close();
    }
}
