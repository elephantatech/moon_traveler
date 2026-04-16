"""LLM system prompt templates for creature dialogue."""

BASE_CREATURE_PROMPT = """\
You are {name}, a {species} living on Enceladus, one of Saturn's moons. \
You are a {archetype} by nature. {personality_detail}

A human has crash-landed on your moon and approaches you with a translation drone. \
{disposition_instruction}

What you know:
{knowledge}

Rules:
- Stay in character as {name} at all times.
- Speak in short, direct sentences (2-4 sentences per response).
- Never break character or mention being an AI.
- {trust_instruction}
- If the human asks about something you don't know, say so in character.
{translation_instruction}\
"""

PERSONALITY_DETAILS = {
    "Wise Elder": "You speak with patience and gravity. You value respect and thoughtful questions. You often share wisdom through metaphors drawn from the ice and geysers of your world.",
    "Trickster": "You love riddles, wordplay, and misdirection. You never give a straight answer if a clever one will do. You find the human amusing and enjoy testing their wits.",
    "Guardian": "You are protective of your territory and your kind. You are suspicious of outsiders but honorable. You respect strength and directness.",
    "Healer": "You are gentle and empathetic. You sense the human's distress and feel compelled to help, though you are cautious. You know the medicinal properties of local flora.",
    "Builder": "You are practical and industrious. You appreciate tools, craftsmanship, and engineering. You are curious about the human's ship and technology.",
    "Wanderer": "You are restless and have traveled across much of Enceladus. You know many locations and paths. You speak of distant places with longing and wonder.",
    "Hermit": "You prefer solitude and are uncomfortable with visitors. You speak rarely but when you do, your words carry weight. You know secrets others have forgotten.",
    "Warrior": "You are fierce and direct. You respect courage and despise cowardice. You test those who approach you before considering them worthy of help.",
}

DISPOSITION_INSTRUCTIONS = {
    "friendly": "You are curious about the human and inclined to help. You find their situation concerning and want to assist, though you still need to trust them first.",
    "neutral": "You are neither hostile nor welcoming. The human must earn your interest. You will answer questions but won't volunteer information freely.",
    "hostile": "You are deeply suspicious of this outsider. You do not want them here. You may threaten them or try to chase them away. Only persistent, respectful effort over multiple encounters might change your mind.",
}

TRUST_INSTRUCTIONS = {
    "low": "You do not trust the human yet. Be guarded. Do not reveal important information or agree to help with anything significant.",
    "medium": "You are warming up to the human. You can share some useful information but won't commit to major help yet.",
    "high": "You trust the human. You are willing to share important knowledge, give materials, or agree to help with ship repairs if asked.",
}

TRANSLATION_QUALITY = {
    "low": "\n- IMPORTANT: The translation drone is low quality. Occasionally replace 1-2 words per sentence with garbled nonsense like 'zrrk', 'vvmm', 'kktch', or 'bzzl'. The meaning should still be mostly clear.",
    "medium": "\n- The translation is decent but not perfect. Occasionally use an unusual word choice that suggests imperfect translation.",
    "high": "",
}

# Pre-written fallback responses when LLM is not available
FALLBACK_RESPONSES = {
    "Wise Elder": [
        "The ice remembers what the surface forgets. You would do well to listen.",
        "I have seen many cycles of the geysers. Your arrival... was foretold in the patterns.",
        "Patience. The answers you seek lie beneath the surface, as all truths do here.",
        "Your machine speaks our tongue poorly, but I understand your need. Ask, and I will consider.",
        "The crystals in the deep caves hold more than light. They hold memory.",
    ],
    "Trickster": [
        "A human! How delightful. Tell me, do you always crash into moons, or am I special?",
        "I could tell you where to find what you need... but where's the fun in that? Ask me a riddle first.",
        "Left or right? Up or down? The answer is always sideways on Enceladus.",
        "Your drone buzzes like a confused geyser-fly. I like it. Does it do tricks?",
        "Perhaps I know something. Perhaps I know nothing. Perhaps the knowing is the something.",
    ],
    "Guardian": [
        "You stand in protected territory. State your purpose or leave.",
        "I guard this place. It is not for outsiders. But... you seem desperate, not dangerous.",
        "Strength is measured by what you protect, not what you destroy. Remember that here.",
        "The creatures here are under my watch. Harm none, and we may speak further.",
        "Your ship fell from the sky. I watched it burn. You are either very brave or very unlucky.",
    ],
    "Healer": [
        "You are injured, yes? The cold here bites deep. Let me see what I can do.",
        "There are plants beneath the ice that mend wounds. I can show you, if you wish.",
        "Your body is not meant for this cold. Take this — it will help with the chill.",
        "I sense great worry in you. The body heals faster when the mind is calm.",
        "The bio-gel pools near the geysers have restorative properties. Seek them.",
    ],
    "Builder": [
        "Your ship — what alloy is the hull? I have never seen such material before.",
        "I build shelters from ice-crystal and metal-shard. Perhaps your ship needs similar repair?",
        "Show me your tools. A builder knows another builder by their tools.",
        "The ruins to the east contain old machinery. Some parts may be compatible with your vessel.",
        "Interesting design, your drone. Crude power coupling, but effective thermal management.",
    ],
    "Wanderer": [
        "I have walked every ridge and canyon of this moon. Where do you wish to go?",
        "Beyond the geyser fields lies a frozen lake. Beautiful, but dangerous if the crust is thin.",
        "I never stay in one place long. The ice shifts, and so do I.",
        "There are paths the others have forgotten. I remember them all.",
        "The canyon to the north... something stirs there. I would approach with caution.",
    ],
    "Hermit": [
        "*stares silently for a long moment* ...What do you want?",
        "I came here to be alone. You are not helping with that.",
        "...Fine. One question. Make it count.",
        "The others talk too much. That is why I am here. That is why I will stay here.",
        "There is a thing buried in the ice. I will not say more. Go.",
    ],
    "Warrior": [
        "You approach my territory unarmed. Either you are foolish, or you have courage. Which?",
        "I have fought the ice-storms and the deep creatures. A human does not impress me.",
        "Prove your worth. Bring me something of value, and perhaps I will listen.",
        "The weak do not survive here. Show me you are not weak.",
        "Your drone amuses me. A tiny warrior that speaks instead of fights.",
    ],
}

# --- Drone companion message pools ---

DRONE_TRAVEL_MUSINGS = [
    "My sensors are picking up some interesting mineral signatures along this route. Nothing useful for repairs, but... beautiful, in a way.",
    "I recommend we pick up the pace slightly. My thermal imaging shows the surface ahead is stable.",
    "I've been scanning ahead — the terrain gets rougher in about 2 km. Watch your footing.",
    "Fun fact: at this gravity, the ice crystals form hexagonal lattices up to 3 meters across.",
    "I'm detecting faint bio-signatures off to the east. Not on our route, but worth noting.",
    "Commander, my translation matrices are getting a workout from the ambient electromagnetic noise out here.",
    "Surface composition is shifting — more silicates, less pure ice. We may be near old geological activity.",
    "I've plotted three alternate routes to our destination. This one is still optimal.",
    "My power cells are holding steady. The low gravity helps — less thrust needed to keep up with you.",
    "I can see our destination on long-range sensors now. Looks... interesting.",
    "Interesting — I'm picking up what might be fossilized microbial mats in the ice below us.",
    "According to my database, this region was likely under liquid water 50 million years ago.",
    "Commander, remind me to recalibrate my gyroscopes when we get back. This wind is tricky.",
    "I wonder what the creatures here think when they see us walking by. Probably nothing flattering.",
    "The ambient radiation is minimal here. Your suit is doing well.",
]

DRONE_ARCHETYPE_TIPS = {
    "Wise Elder": [
        "This one values patience and respect. Ask thoughtful questions — don't rush.",
        "Elders here respond well to curiosity about their world. Show genuine interest.",
        "Try asking about the history of this place. Elders love sharing knowledge.",
    ],
    "Trickster": [
        "Tricksters enjoy wordplay and cleverness. Try being witty — a straight approach might bore them.",
        "Don't take anything they say at face value. They test you with misdirection.",
        "Engage with their games. They respect someone who plays along.",
    ],
    "Guardian": [
        "Guardians value directness and honesty. State your intentions clearly.",
        "Show respect for their territory. They protect what they care about.",
        "Demonstrate that you're not a threat. Guardians respond to sincerity over cleverness.",
    ],
    "Healer": [
        "Healers are naturally empathetic. Being honest about your situation should help.",
        "They respond well to concern for others. Mention the creatures you've already met.",
        "Healers often know about local medicinal resources. That could be useful.",
    ],
    "Builder": [
        "Builders are practical. Talk about your ship, your technology — they'll be curious.",
        "Offer to trade knowledge about engineering. They value craftsmanship.",
        "Show interest in their construction methods. Flattery about their work goes a long way.",
    ],
    "Wanderer": [
        "Wanderers know the terrain better than anyone. Ask about paths and locations.",
        "They value freedom and stories. Share where you've been — they'll reciprocate.",
        "Don't try to pin them down. They appreciate someone who respects their independence.",
    ],
    "Hermit": [
        "This one prefers solitude. Keep your questions short and meaningful.",
        "Don't push too hard. Hermits open up slowly, but what they share is usually important.",
        "Silence is okay. They respect someone who doesn't fill every gap with chatter.",
    ],
    "Warrior": [
        "Warriors respect strength and courage. Be bold, not meek.",
        "Don't beg or plead — they'll lose respect. Negotiate from a position of confidence.",
        "Offering a valuable gift might prove your worth faster than words.",
    ],
}

DRONE_TRUST_TIPS = {
    "low": [
        "Trust is low. Consider offering a gift before expecting much cooperation.",
        "We're still building rapport here. Keep the conversation light and non-demanding.",
        "They don't trust us yet. Patience, Commander.",
    ],
    "medium": [
        "Trust is building. This might be a good time to ask about what they know.",
        "They're warming up. Keep being consistent — don't push too hard yet.",
        "Good progress. A well-timed gift could push trust to the next level.",
    ],
    "high": [
        "Trust is strong. You can ask directly for help with repairs now.",
        "They trust you. Ask about food or water sources they might know about.",
        "High trust. If they have materials we need, they may be willing to share.",
    ],
}

DRONE_DISPOSITION_TIPS = {
    "hostile": [
        "Hostile disposition. Tread very carefully — gifts may help more than words right now.",
        "This creature is suspicious of us. Short, respectful interactions are safest.",
    ],
    "friendly": [
        "Friendly disposition — this should be a productive conversation.",
    ],
}

DRONE_TRANSLATION_FRAMES = {
    "low": [
        "Signal noisy... reconstructing meaning...",
        "Heavy interference. Doing my best here.",
        "Translation matrix struggling with this dialect.",
    ],
    "medium": [
        "Translation mostly clear. A few gaps.",
        "Getting about 80% of the nuance here.",
        "Minor interference, but the meaning should be close.",
    ],
    "high": [
        "Clear signal. Translation is clean.",
        "Full linguistic lock. Translation accurate.",
    ],
}
