// This is a read-only preview, not a promise that a moving player or block will stay put.
export async function inspectRoute(bot, target, distance = 2, module) {
    if (!bot.pathfinder?.getPathFromTo || !bot.entity?.position) return { status: 'unavailable' };
    const { Movements, goals } = module ?? await import('mineflayer-pathfinder');
    const movements = new Movements(bot);
    movements.canDig = false;
    movements.allow1by1towers = false;
    movements.scafoldingBlocks = [];
    movements.allowParkour = false;
    movements.canOpenDoors = false;
    movements.maxDropDown = Math.min(movements.maxDropDown ?? 3, 3);
    bot.pi_terrainGuard?.(movements);
    const goal = new goals.GoalNear(target.x, target.y, target.z, distance);
    const search = bot.pathfinder.getPathFromTo(movements, bot.entity.position, goal, {timeout: 300, tickTimeout: 40, searchRadius: 64, optimizePath: false});
    let result, iterations = 0;
    const start = Date.now();
    do {
        result = search.next().value?.result;
        iterations++;
    } while (result?.status === 'partial' && iterations < 6 && Date.now() - start < 300);
    if (!result) return {status: 'unavailable'};
    const rawPath = (result.path ?? []).map(p => [p.x, p.y, p.z]);
    // Some pathfinder moves can include falls larger than the allowed drop (e.g. when spawned in air).
    // Never offer those nodes as walking waypoints.
    const startY = Math.floor(bot.entity.position.y);
    const unsafeIndex = rawPath.findIndex((p, i) => (i ? rawPath[i - 1][1] : startY) - p[1] > 3);
    const path = unsafeIndex < 0 ? rawPath : rawPath.slice(0, unsafeIndex);
    const waypoints = [];
    for (let i = 0; i < path.length; i++) {
        const prev = path[i - 1], cur = path[i], next = path[i + 1];
        if (!prev || !next || cur[0] - prev[0] !== next[0] - cur[0] || cur[1] - prev[1] !== next[1] - cur[1] || cur[2] - prev[2] !== next[2] - cur[2]) waypoints.push(cur);
    }
    const status = unsafeIndex >= 0 ? 'search_incomplete' : result.status === 'success' ? 'route_found' : result.status === 'noPath' ? 'no_route_found' : 'search_incomplete';
    return {
        status,
        target: [target.x, target.y, target.z],
        distance,
        waypoints: waypoints.slice(0, 12),
        ...(waypoints.length > 12 ? {moreWaypoints: true} : {}),
        ...(unsafeIndex >= 0 ? {warning: 'Omitted an unsafe drop from the preview.'} : {}),
        ...(status !== 'route_found' && path.length ? {closestSearched: path.at(-1)} : {}),
        note: 'Preview only: no digging, block placement, opening doors or parkour; moving obstacles and terrain changes can invalidate it. Limited search is not proof that no route exists.',
    };
}
