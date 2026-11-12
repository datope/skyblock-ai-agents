export function startupCommands({ worldExists, world, seed }) {
    const commands = worldExists && world === 'void' ? [] : ['time set day'];
    if (world === 'void') commands.push('difficulty easy');
    if (!worldExists && world === 'void') {
        commands.push(
            'gamerule spawnRadius 0', 'gamerule keepInventory false', 'gamerule sendCommandFeedback false',
            // The 6x6 L-shaped classic island doubled in both horizontal dimensions.
            'fill -5 62 -5 0 63 6 minecraft:dirt',
            'fill 1 62 1 6 63 6 minecraft:dirt',
            'fill -5 64 -5 0 64 6 minecraft:grass_block',
            'fill 1 64 1 6 64 6 minecraft:grass_block',
            'setblock -3 62 3 minecraft:bedrock',
            'setworldspawn 0 65 4',
            'fill -5 68 2 -1 70 6 minecraft:oak_leaves[persistent=false]',
            'fill -4 71 3 -2 71 5 minecraft:oak_leaves[persistent=false]',
            'fill -3 65 4 -3 68 4 minecraft:oak_log',
            'setblock -2 65 -4 minecraft:chest[facing=south]{Items:[{Slot:0b,id:"minecraft:lava_bucket",count:1},{Slot:1b,id:"minecraft:ice",count:1}]}',
            // Load the distant chunk and support the sand against gravity.
            'forceload add 64 0',
            'fill 64 61 0 66 61 2 minecraft:sandstone',
            'fill 64 62 0 66 64 2 minecraft:sand',
            'setblock 64 65 0 minecraft:cactus',
            'setblock 66 65 0 minecraft:chest[facing=south]{Items:[{Slot:0b,id:"minecraft:pumpkin_seeds",count:1},{Slot:1b,id:"minecraft:melon_seeds",count:1},{Slot:2b,id:"minecraft:obsidian",count:10},{Slot:3b,id:"minecraft:iron_ingot",count:1}]}',
            'setblock 65 65 2 minecraft:gravel',
            'forceload remove 64 0',
            'say Skyblock: one team, one diamond. Put one diamond in the starter chest at -2 65 -4. Use research and exploration to find diamonds.',
        );
    } else if (!worldExists && world === 'normal' && seed === '2024') {
        commands.push('setworldspawn 5 71 -3', 'gamerule spawnRadius 0');
    }
    return commands;
}
