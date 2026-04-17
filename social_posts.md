# Social posts -- Moon Traveler Terminal

---

## Twitter/X

I wanted to see what happens when you give every NPC in a game its own local LLM and let it remember things.

So I built a terminal survival game to find out. You crash on Saturn's moon. Your ship is broken. The aliens who live there might help you fix it, but they don't trust you yet.

Each creature runs on Qwen 3.5 or Gemma 4, locally on your machine. No API calls. They have roles -- a Healer will patch you up immediately, a Hermit won't talk to you until you've earned it. Trust goes from 0 to 100 and you earn it one conversation at a time.

The part I'm most interested in: after every conversation, the LLM writes a short memory summary for that creature. What did the player say their name was? What did they ask for? Did they bring a gift? Next time you visit, the creature actually references those things. It's stored as markdown in SQLite -- cheap, persistent, works offline.

The whole thing runs on your hardware. No cloud. A 2B model on CPU is enough.

Looking for people to break it.

https://github.com/elephantatech/moon_traveler
https://elephantatech.github.io/moon_traveler/

curl -fsSL https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.sh | bash

#LocalAI #LLM #GameDev #Python #OpenSource

---

## LinkedIn

I spent the last few weeks building a game where every NPC is a local LLM agent with its own memory. Partly because I wanted to play it, partly because I wanted to understand the engineering problems.

The game is Moon Traveler Terminal. Text-based, runs in a terminal. You crash-land on Enceladus (Saturn's icy moon), your ship is wrecked, and the only path home is convincing alien creatures to help you. Each creature runs on a local model -- Qwen 3.5 2B or Gemma 4 E2B, your choice. No internet, no API keys.

Here's what I found interesting while building it:

The memory problem. Sending full conversation history to a 2B model eats context fast and the creature "forgets" anything outside the window. So after each conversation, I have the LLM write a structured summary -- who is this player, what did they want, what promises were made, what items changed hands. That summary (maybe 200 tokens of markdown) gets injected into the system prompt on the next visit. The creature references things from three conversations ago without needing 5000 tokens of chat replay. It's stored in SQLite alongside the save file.

Trust as a gating mechanism. Each creature has an archetype (Healer, Merchant, Builder, Hermit, etc.) and a trust score from 0 to 100. The archetype determines what they can give you and at what trust level. A Healer helps at trust 0 because that's who they are. A Hermit has rare materials but won't share until trust 80. A Merchant will trade at trust 20 but never gives anything for free. The LLM generates both dialogue and action decisions (heal, trade, hand over materials) in a single inference call based on the trust level and memory context.

There's also a drone companion that whispers private hints the creature can't "hear" -- it knows what you need and what the creature can provide. Second, shorter LLM call. Falls back to templates when the model isn't loaded.

Stack: Python, llama-cpp-python, Rich, SQLite. GPU auto-detect with CPU fallback. Cross-platform installers, no Python required for pre-built binaries.

It's in beta. I'm looking for feedback -- especially from people who've worked on agent memory, local inference, or game AI. What breaks? What feels wrong? What would you do differently?

https://github.com/elephantatech/moon_traveler
https://elephantatech.github.io/moon_traveler/

Install (no Python needed):
curl -fsSL https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.sh | bash

Windows PowerShell:
irm https://raw.githubusercontent.com/elephantatech/moon_traveler/main/install.ps1 | iex

#LocalAI #LLM #GameDev #Python #OpenSource
