import { withFailureCode } from '../tools/game/failures.js';
import { TEAM_VOTERS } from './shared-goal.js';

// During the generator goal, reserve terrain changes for the elected builder.
// Helpers can gather logs, craft, handle chests, communicate or wait.
export function guardGeneratorWork({ teamGoal, agent, tool, args = {}, active }) {
    if (!TEAM_VOTERS.includes(agent)) return;
    const goal = teamGoal.current();
    if (!(goal.id === 'initial' || /generat|генератор/i.test(goal.goal))) return;
    const excavation = new Set(['place', 'place_block', 'place_batch', 'place_line', 'break_block', 'break_batch', 'break_area']);
    const naturalMaterials = /^(?:.*_logs?|.*_leaves|.*_saplings?)$/;
    const risky = excavation.has(tool) || (tool === 'gather' && !naturalMaterials.test(args.block ?? '')) ||
        (tool === 'interact_block' && active?.heldItem) || tool === 'use_item';
    if (!risky) return;
    const builder = teamGoal.builder(goal.id);
    if (!builder)
        throw withFailureCode(new Error('Generator work is paused until ChatGPT, Claude and DeepSeek all vote using vote_team_builder. Inspect teamElection and vote; gather logs, craft, or wait.'), 'action_failed');
    if (builder.builder !== agent)
        throw withFailureCode(new Error(`Only elected builder ${builder.builder} may dig, place blocks or use items for the generator. Gather logs, craft, deliver supplies or wait.`), 'action_failed');
}
