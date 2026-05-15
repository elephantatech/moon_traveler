# Trickster Gambles - Feature Specification

## Overview
Players can stake items for a chance at better rewards, adding risk/reward mechanics to the game.

## Mechanics

### Basic Gamble
- Player stakes an item from inventory
- A random outcome determines the result
- Possible outcomes: Better item, Same item, Worse item, Nothing

### Outcome Probabilities
| Stake Value | Win Better | Keep Same | Lose | Big Win |
|-------------|-----------|-----------|------|---------|
| Common | 35% | 30% | 30% | 5% |
| Uncommon | 30% | 25% | 35% | 10% |
| Rare | 25% | 20% | 40% | 15% |
| Legendary | 20% | 15% | 45% | 20% |

### Anti-Addiction Safeguards
- Maximum 10 gambles per game day
- Cooldown period between gambles (5 minutes)
- Loss streak protection: After 3 consecutive losses, next gamble has +20% win rate
- Daily loss cap: Player cannot lose more than 50% of inventory value per day

### UI Elements
1. **Gamble Shrine**: Location in game world where gambling takes place
2. **Stake Slot**: Drag item here to stake
3. **Wheel Animation**: Visual feedback for outcome
4. **History Log**: Last 10 gamble results
5. **Statistics**: Win rate, biggest win, total staked

### Implementation Notes
```gdscript
class_name TricksterGamble

var daily_gambles: int = 0
var max_daily_gambles: int = 10
var loss_streak: int = 0
var daily_losses: float = 0.0

func can_gamble() -> bool:
    return daily_gambles < max_daily_gambles

func calculate_outcome(item_rarity: String) -> Dictionary:
    var base_probs = PROBABILITY_TABLE[item_rarity]
    if loss_streak >= 3:
        base_probs["win_better"] += 0.20
    return weighted_random(base_probs)
```

### Save Data
```json
{
  "gamble_state": {
    "daily_gambles": 5,
    "loss_streak": 2,
    "daily_losses": 150.0,
    "last_reset": "2026-05-16",
    "history": [
      {"item": "Iron Sword", "outcome": "better", "result": "Steel Sword", "timestamp": "..."},
    ]
  }
}
```
