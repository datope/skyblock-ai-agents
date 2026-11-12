// Only system messages emitted by the local voice bridge match this format.
export function parseVoiceChat(message, position, sender) {
    if (sender != null || position === 'chat') return null;
    return /^<Krebes> \(голос\) (.+)$/.exec(String(message))?.[1] ?? null;
}
