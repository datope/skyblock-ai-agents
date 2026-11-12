import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

// Role rules live next to the scenario, in the project root, so they can be
// rewritten without touching code. Names are fixed by the session controller.
const ROOT = () => path.join(process.cwd(), 'psy');

export function psyRole(name) {
    if (name === 'DeepSeek') return 'psychiatrist';
    if (name === 'Claude') return 'patient';
    return null;
}

export function psyRules(name) {
    const role = psyRole(name);
    if (!role) return '';
    const file = path.join(ROOT(), `rules-${role}.md`);
    if (!existsSync(file)) return '';
    return readFileSync(file, 'utf8').trim();
}
