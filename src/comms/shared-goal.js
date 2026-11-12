import { appendFileSync, closeSync, existsSync, mkdirSync, openSync, readFileSync, statSync, unlinkSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import path from 'node:path';

export const TEAM_VOTERS = Object.freeze(['ChatGPT', 'Claude', 'DeepSeek']);
export const BUILDER_CANDIDATES = TEAM_VOTERS;
export const COMMANDER = 'Claude';

export function requireCommander(author) {
    if (author !== COMMANDER) throw new Error('Claude is the commander and manages team goals and steps. Send Claude your status or blocker.');
}

export const INITIAL_GOAL = Object.freeze({ id: 'initial', goal: 'Вместе добыть булыжник на существующем генераторе и подготовить материалы для моста к песчаному острову.', author: 'team', note: 'Все вместе продвигают одну задачу, выбирая дополняющие действия.' });

export class SharedGoal {
    constructor(root) { this.root = root; this.file = path.join(root, 'team-goals.jsonl'); this.lock = path.join(root, 'team-goal.lock'); mkdirSync(root, { recursive: true }); }
    current() {
        if (!existsSync(this.file)) return { ...INITIAL_GOAL };
        const lines = readFileSync(this.file, 'utf8').split('\n');
        for (let i = lines.length - 1; i >= 0; i--) {
            if (!lines[i].trim()) continue;
            try { const entry = JSON.parse(lines[i]); if (entry.id && entry.goal) return entry; } catch { /* Ignore incomplete records. */ }
        }
        return { ...INITIAL_GOAL };
    }
    plan(goalId = this.current().id) {
        if (!/^[A-Za-z0-9-]+$/.test(goalId)) return null;
        try {
            const lines = readFileSync(path.join(this.root, `steps-${goalId}.jsonl`), 'utf8').split('\n');
            for (let i = lines.length - 1; i >= 0; i--) {
                if (!lines[i].trim()) continue;
                try { const plan = JSON.parse(lines[i]); if (plan.goalId === goalId && plan.id && Array.isArray(plan.steps)) return plan; }
                catch { /* Ignore incomplete records. */ }
            }
        } catch (e) { if (e.code !== 'ENOENT') throw e; }
        return null;
    }
    setPlan({ expectedGoalId, expectedPlanId, steps, author }) {
        requireCommander(author);
        if (!/^[A-Za-z0-9-]+$/.test(expectedGoalId) || !/^[A-Za-z0-9-]+$/.test(expectedPlanId)) throw new Error('Invalid plan or goal id.');
        if (!Array.isArray(steps) || steps.length < 1 || steps.length > 5) throw new Error('Choose 1 to 5 short steps.');
        const clean = steps.map(step => {
            const task = String(step.task ?? '').trim();
            const evidence = String(step.evidence ?? '').trim();
            if (!task || task.length > 120 || !['any', ...TEAM_VOTERS].includes(step.owner) ||
                !['todo', 'doing', 'done', 'blocked'].includes(step.status) || evidence.length > 160 ||
                (step.status === 'done' && !evidence)) throw new Error('Invalid step: done requires observed evidence.');
            return { task, owner: step.owner, status: step.status, ...(evidence ? { evidence } : {}) };
        });
        let fd;
        try {
            try { fd = openSync(this.lock, 'wx'); }
            catch (e) {
                if (e.code !== 'EEXIST') throw e;
                try { if (Date.now() - statSync(this.lock).mtimeMs > 30000) unlinkSync(this.lock); } catch (err) { if (err.code !== 'ENOENT') throw err; }
                try { fd = openSync(this.lock, 'wx'); } catch (err) { if (err.code === 'EEXIST') throw new Error('A teammate is updating the shared goal or steps. Re-observe and retry.'); throw err; }
            }
            const goal = this.current();
            if (goal.id !== expectedGoalId) return { changed: false, goal, note: 'Goal changed; observe again.' };
            const previous = this.plan(goal.id);
            if ((previous?.id ?? 'none') !== expectedPlanId) return { changed: false, plan: previous, note: 'A teammate changed the steps; observe again.' };
            const plan = { id: randomUUID(), goalId: goal.id, author, updatedAt: new Date().toISOString(), steps: clean };
            appendFileSync(path.join(this.root, `steps-${goal.id}.jsonl`), JSON.stringify(plan) + '\n', { encoding: 'utf8', mode: 0o600 });
            return { changed: true, plan };
        } finally {
            if (fd !== undefined) { closeSync(fd); try { unlinkSync(this.lock); } catch (e) { if (e.code !== 'ENOENT') throw e; } }
        }
    }
    election(goalId = this.current().id) {
        if (!/^[A-Za-z0-9-]+$/.test(goalId)) return null;
        const initial = { goalId, round: 1, votes: {}, winner: null };
        try {
            const lines = readFileSync(path.join(this.root, `election-v2-${goalId}.jsonl`), 'utf8').split('\n');
            for (let i = lines.length - 1; i >= 0; i--) {
                if (!lines[i].trim()) continue;
                try { const state = JSON.parse(lines[i]); if (state.goalId === goalId && state.round && state.votes) return state; }
                catch { /* Ignore incomplete final records. */ }
            }
        } catch (e) { if (e.code !== 'ENOENT') throw e; }
        return initial;
    }
    builder(goalId = this.current().id) {
        const election = this.election(goalId);
        return BUILDER_CANDIDATES.includes(election?.winner) ? { goalId, builder: election.winner, round: election.round } : null;
    }
    voteBuilder({ expectedId, expectedRound, candidate, author }) {
        if (!TEAM_VOTERS.includes(author)) throw new Error('Only ChatGPT, Claude and DeepSeek can vote.');
        if (!BUILDER_CANDIDATES.includes(candidate)) throw new Error('Builder must be ChatGPT, Claude or DeepSeek.');
        if (!/^[A-Za-z0-9-]+$/.test(expectedId)) throw new Error('Invalid goal id.');
        let fd;
        try {
            try { fd = openSync(this.lock, 'wx'); }
            catch (e) {
                if (e.code !== 'EEXIST') throw e;
                try { if (Date.now() - statSync(this.lock).mtimeMs > 30000) unlinkSync(this.lock); } catch (err) { if (err.code !== 'ENOENT') throw err; }
                try { fd = openSync(this.lock, 'wx'); } catch (err) { if (err.code === 'EEXIST') throw new Error('A teammate is updating the vote. Re-observe and retry.'); throw err; }
            }
            const current = this.current();
            if (current.id !== expectedId) return { recorded: false, current, note: 'Goal changed; observe again.' };
            const previous = this.election(expectedId);
            if (previous.winner) return { recorded: false, election: previous, note: 'The team has already elected a builder.' };
            if (previous.round !== expectedRound) return { recorded: false, election: previous, note: 'Voting round changed; observe before voting.' };
            if (previous.votes[author]) return { recorded: false, election: previous, note: 'You already voted in this round.' };
            const votes = { ...previous.votes, [author]: candidate };
            const allVoted = TEAM_VOTERS.every(name => votes[name]);
            let state = { goalId: expectedId, round: previous.round, votes, winner: null };
            let note = 'Wait for all three votes before building.';
            if (allVoted) {
                const winner = BUILDER_CANDIDATES.find(name => Object.values(votes).filter(v => v === name).length >= 2);
                if (winner) { state.winner = winner; note = 'All three voted; the majority selected one builder.'; }
                else { state = { goalId: expectedId, round: previous.round + 1, votes: {}, winner: null, previousRound: votes }; note = 'Three different choices: vote again in the new round.'; }
            }
            appendFileSync(path.join(this.root, `election-v2-${expectedId}.jsonl`), JSON.stringify(state) + '\n', { encoding: 'utf8', mode: 0o600 });
            return { recorded: true, election: state, note };
        } finally {
            if (fd !== undefined) { closeSync(fd); try { unlinkSync(this.lock); } catch (e) { if (e.code !== 'ENOENT') throw e; } }
        }
    }
    set({ expectedId, goal, reason, author }) {
        requireCommander(author);
        goal = String(goal ?? '').trim(); reason = String(reason ?? '').trim();
        if (!goal || goal.length > 200 || !reason || reason.length > 240) throw new Error('Goal and reason must be nonempty and concise.');
        let fd;
        try {
            try { fd = openSync(this.lock, 'wx'); }
            catch (e) {
                if (e.code !== 'EEXIST') throw e;
                try { if (Date.now() - statSync(this.lock).mtimeMs > 30000) unlinkSync(this.lock); } catch (err) { if (err.code !== 'ENOENT') throw err; }
                try { fd = openSync(this.lock, 'wx'); } catch (err) { if (err.code === 'EEXIST') throw new Error('A teammate is updating the goal. Re-observe and try again.'); throw err; }
            }
            const previous = this.current();
            if (previous.id !== expectedId) return { changed: false, current: previous, note: 'A teammate already changed the goal; work on the current one.' };
            const current = { id: randomUUID(), goal, reason, author, updatedAt: new Date().toISOString() };
            appendFileSync(this.file, JSON.stringify(current) + '\n', { encoding: 'utf8', mode: 0o600 });
            return { changed: true, current };
        } finally {
            if (fd !== undefined) { closeSync(fd); try { unlinkSync(this.lock); } catch (e) { if (e.code !== 'ENOENT') throw e; } }
        }
    }
}
