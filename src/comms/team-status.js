import { mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';

export const TEAM_NAMES = ['ChatGPT', 'Claude', 'DeepSeek'];
export class TeamStatus {
    constructor(root, name) {
        this.dir = path.join(root, 'team-status'); this.name = name;
        mkdirSync(this.dir, { recursive: true });
    }
    publish(bot) {
        if (!TEAM_NAMES.includes(this.name) || !bot.entity?.position || !bot.inventory?.items) return;
        const totals = {};
        for (const item of bot.inventory.items()) totals[item.name] = (totals[item.name] ?? 0) + item.count;
        const p = bot.entity.position;
        const snapshot = { name: this.name, updatedAt: Date.now(), dimension: bot.game?.dimension ?? null,
            position: { x: p.x, y: p.y, z: p.z }, health: bot.health, food: bot.food, inventory: totals };
        const file = path.join(this.dir, `${this.name}.json`), tmp = `${file}.${process.pid}.tmp`;
        writeFileSync(tmp, JSON.stringify(snapshot), { mode: 0o600 }); renameSync(tmp, file);
    }
    read(now = Date.now()) {
        return TEAM_NAMES.map(name => {
            try {
                const data = JSON.parse(readFileSync(path.join(this.dir, `${name}.json`), 'utf8'));
                const ageSeconds = Math.max(0, Math.floor((now - data.updatedAt) / 1000));
                if (data.name !== name || !Number.isFinite(data.updatedAt) || ageSeconds > 15)
                    return { name, status: 'offline_or_stale', inventory: null };
                return { ...data, ageSeconds, status: 'recent_snapshot' };
            } catch { return { name, status: 'offline_or_stale', inventory: null }; }
        });
    }
}
