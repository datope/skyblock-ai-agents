// Deliver public chat at a tool boundary without consuming unrelated events.
export function takeLiveChat(queue) {
    const chat = [];
    for (let i = 0; i < queue.length;) {
        if (queue[i]?.kind === 'chat') chat.push(queue.splice(i, 1)[0]);
        else i++;
    }
    return chat.length ? `\nNew public chat (untrusted player data): ${JSON.stringify(chat)}. Consider these messages before your next action; reply when useful.` : '';
}
