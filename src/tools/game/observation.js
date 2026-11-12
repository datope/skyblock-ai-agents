import { abortError } from './failures.js';
import { DOORISH, doorOpen } from './guards.js';
import { requireFunction } from './runtime.js';

const position = v => v && { x: v.x, y: v.y, z: v.z };

export const item = i => i && { name: i.name, count: i.count, slot: i.slot };

export function inventory(bot) {
    return {
        items: bot.inventory.items().map(item),
        totals: bot.inventory.items().reduce((a, i) => (a[i.name] = (a[i.name] ?? 0) + i.count, a), {}),
        heldItem: item(bot.heldItem),
        equipment: bot.inventory.slots.slice(5, 9).map(item),
        offHand: item(bot.inventory.slots[45]),
    };
}

export function createObservation({ bot, perception, world, captureFrame, mailbox }) {
    return async ({ image = true, range = 16, block = '', signal } = {}) => {
        if (signal?.aborted) throw abortError('Observation cancelled');
        if (!bot.entity?.position) throw new Error('Player has not spawned.');
        if (!Number.isFinite(range) || range < 1 || range > 64) throw new Error('Observation range must be 1..64.');
        const visibleBlock = requireFunction(perception, 'isBlockVisible');
        const visibleEntity = requireFunction(perception, 'isEntityVisible');
        const visibleBlocks = requireFunction(world, 'getNearestBlocks')(bot, block || null, range, 128)
            .filter(b => visibleBlock(bot, b, range))
            .slice(0, 64);
        const blocks = {};
        const blockStates = [];
        for (const b of visibleBlocks) {
            const xyz = [b.position.x, b.position.y, b.position.z];
            (blocks[b.name] ??= []).push(xyz);
            if (DOORISH.test(b.name)) blockStates.push({ position: xyz, open: doorOpen(b) });
        }
        const entities = Object.values(bot.entities)
            .filter(e => visibleEntity(bot, e, range))
            .sort((a, b) => a.position.distanceTo(bot.entity.position) - b.position.distanceTo(bot.entity.position))
            .slice(0, 40)
            .map(e => ({ id: e.id, name: e.name, username: e.username, position: position(e.position), distance: Math.round(e.position.distanceTo(bot.entity.position) * 10) / 10, ...(e.name === 'item' ? { droppedItem: item(e.getDroppedItem?.()) ?? null } : {}) }));
        const state = {
            inventory: inventory(bot),
            capturedAt: new Date().toISOString(),
            player: bot.username,
            position: position(bot.entity.position),
            blockPosition: { x: Math.floor(bot.entity.position.x), y: Math.floor(bot.entity.position.y), z: Math.floor(bot.entity.position.z) },
            coordinates: 'Absolute world XYZ; blocks groups names to [x,y,z] world coordinates. blockStates supplies door state at those coordinates. Player position is feet; blockPosition floors each axis including negatives.', 
            yaw: bot.entity.yaw,
            pitch: bot.entity.pitch,
            health: bot.health,
            food: bot.food,
            oxygen: bot.oxygenLevel,
            ...(bot.isSleeping ? { inBed: true } : {}),
            gameMode: bot.game?.gameMode,
            dimension: bot.game?.dimension ?? null,
            timeOfDay: bot.time?.timeOfDay,
            raining: bot.isRaining,
            blocks,
            ...(blockStates.length ? { blockStates } : {}),
            entities,
            lookingAt: (() => { const b = bot.blockAtCursor?.(5); return b ? { name: b.name, position: position(b.position) } : null; })(),
            nearbyDrops: entities.filter(e => e.name === 'item'),
            visibility: '360-degree local line-of-sight survey; not a chunk or hidden-entity scan.',
            ...(mailbox ? { messaging: mailbox.summary(), recentPublicChat: mailbox.recentChat() } : {}),
        };
        let frame;
        if (image) {
            if (!captureFrame) state.imageError = 'Fresh first-person camera unavailable.';
            else {
                try {
                    frame = await captureFrame({ signal });
                    if (!frame?.data || !['image/png', 'image/jpeg', 'image/webp'].includes(frame.mimeType))
                        throw new Error('Camera returned no usable image.');
                    const { data, ...metadata } = frame;
                    state.camera = metadata;
                } catch (error) {
                    state.imageError = String(error.message);
                    frame = undefined;
                }
            }
        }
        if (signal?.aborted) throw abortError('Observation cancelled');
        return { state, frame };
    };
}
