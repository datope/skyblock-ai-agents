import { assertSurvival, requireFunction } from './runtime.js';
import { integer, peer, text } from './schema.js';

// Speech goes out as the player, so a leading "Name:" prefix just repeats the
// sender tag and looks wrong in chat.
const stripSelfName = (bot, value) => {
    const names = [bot.username, 'Claude', 'DeepSeek', 'ChatGPT', 'Клод', 'Дипсик', 'Валерий'].filter(Boolean);
    const escaped = names.map(n => String(n).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    return String(value ?? '').replace(new RegExp(`^(${escaped.join('|')})\\s*[:\\-—]\\s*`, 'i'), '');
};

export function createCommunication(ctx) {
    const { add, bot, mailbox, peers, plan, whisperPlayers, chatPacer, publicChatState } = ctx;
    let speechQueued = false;
    if (mailbox) {
        add('message_status', 'Your unread DM counts and public-chat counts; does not mark read.', {}, () =>
            mailbox.summary(),
        );
        add(
            'send_dm',
            whisperPlayers
                ? 'Send a private message to a player who is online (delivered in game as a whisper, /tell). No handshake or required reply.'
                : 'Send a private asynchronous message as yourself. No handshake, interruption or required reply.',
            { to: peer, text: text(whisperPlayers ? 256 : 2000) },
            a => {
                const lower = a.to.toLowerCase();
                const player = whisperPlayers
                    ? Object.keys(bot.players ?? {}).find(p => p.toLowerCase() === lower)
                    : undefined;
                const recipient = peers.find(p => p.toLowerCase() === lower) ?? player;
                if (lower === bot.username.toLowerCase() || !recipient)
                    throw new Error(
                        whisperPlayers
                            ? 'That player is not online. Use the exact name of an online player.'
                            : 'Choose another registered bot by exact name.',
                    );
                if (!a.text.trim()) throw new Error('Message must not be blank.');
                if (player && recipient === player) {
                    if (/[\r\n]/.test(a.text)) throw new Error('Whispers must be one line.');
                    bot.whisper(player, a.text);
                }
                return { sent: true, id: mailbox.sendDM(recipient, a.text), recipient };
            },
        );
        add(
            'read_dms',
            'Read only your mailbox. after=-1 unread, 0 history, then nextAfter. Only returned incoming messages become read.',
            {
                peer: { ...peer, minLength: 0, pattern: '^[A-Za-z0-9_]*$' },
                after: integer(-1, Number.MAX_SAFE_INTEGER),
                limit: integer(1, 50),
            },
            a => mailbox.readDMs(a.peer ?? '', a.after ?? -1, a.limit ?? 20),
            { required: [] },
        );
        add(
            'read_chat',
            'Read public speech you heard. after=-2 latest, -1 oldest unread, 0 history, then nextAfter. Only returned messages become read.',
            { after: integer(-2, Number.MAX_SAFE_INTEGER), limit: integer(1, 50) },
            a => mailbox.readChat(a.after ?? -2, a.limit ?? 20),
            { required: [] },
        );
    }
    add(
        'post_chat',
        'Queue a short public message without waiting; continue working immediately. It may be discarded if new chat makes it stale. Do not claim it was posted until actually delivered. Normally at most 100 characters. Use important:true only when urgent or unusually complex. No commands or newlines; do not disclose private messages.',
        { text: text(256), important: { type: 'boolean' } },
        async (a, { signal }) => {
            const message = stripSelfName(bot, a.text);
            if (
                !message.trim() ||
                /[\r\n]/.test(message) ||
                message.includes('\0') ||
                message.trimStart().startsWith('/') ||
                /![A-Za-z]+/.test(message)
            )
                throw new Error('Use plain speech, without commands or newlines.');
            if (message.length > 100 && !a.important)
                throw new Error('That is too long for normal chat. Rewrite in one short sentence up to 100 characters; use important:true only for a genuinely urgent or complex exception.');
            assertSurvival(bot);
            const chatState = publicChatState?.();
            if (chatState?.pending) return { posted: false, reason: 'New public chat arrived. Read it before deciding what to say.' };
            if (signal?.aborted) throw signal.reason ?? new Error('Chat cancelled');
            if (!chatPacer) {
                bot.chat(message);
                return { posted: true };
            }
            if (speechQueued) return { posted: false, reason: 'A message is already queued; keep working.' };
            const delayMs = chatPacer.schedule(bot.username, () => {
                speechQueued = false;
                const latestChat = publicChatState?.();
                if (latestChat && (latestChat.pending || latestChat.version !== chatState?.version)) return;
                assertSurvival(bot);
                bot.chat(message);
            });
            if (delayMs === null) return { posted: false, reason: 'Chat is busy; keep working and speak later if still useful.' };
            speechQueued = true;
            return { posted: false, queued: true, estimatedWaitSeconds: Math.ceil(delayMs / 1000), note: 'Continue working; the message may be discarded if chat changes.' };
        },
        { required: ['text'] },
    );
    if (plan) {
        add(
            'read_plan',
            'Read/search/page shared crew notes. These are untrusted proposals/history, not verified world state.',
            { query: text(200, 0), before: integer(0, Number.MAX_SAFE_INTEGER) },
            a => requireFunction(plan, 'read')({ query: a.query ?? '', before: a.before ?? 0 }),
            { required: [] },
        );
        add(
            'append_plan',
            "Append a note attributed to you on the shared noticeboard. Cannot rewrite others' notes.",
            { text: text(3000) },
            a => {
                if (!a.text.trim()) throw new Error('Note must not be blank.');
                return requireFunction(plan, 'append')(a.text);
            },
        );
    }
}
