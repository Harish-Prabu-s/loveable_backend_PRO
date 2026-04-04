# 🏗️ Master Architecture: 9-Mode Unified Social Interaction Engine

This document serves as the high-level system design for the social multiplayer interaction engine, combining state-authoritative gameplay, Redis-backed matchmaking, and real-time WebSocket orchestration.

---

## 1. Core Logic Engine (`SocialGameConsumer`)

A single, unified backend engine handles all modes by switching logic based on the `game_mode` context of the active `GameRoom`.

### Lifecycle States
- **`SpinningWheel`**: suspends gameplay for 2s to build engagement.
- **`TurnAssigned`**: Server selects active player and questioner/host.
- **`InputPhase`**: (Mode-dependent) Questioner captures target task or scenario.
- **`TimerStart`**: Unified 120s server-validated countdown.
- **`ResultPhase`**: Finalizes scoring (+10/5 XP and Relationship points).

---

## 2. Supported Interaction Modes

| Mode | Core Rule | Backend Logic |
| :--- | :--- | :--- |
| **❤️ Romantic** | Bonding focus | Strict "Truth" tasks; questioner must input the prompt. |
| **💬 Deep Questions** | Emotional depth | Truth-only; answers tracked for relationship timeline. |
| **🔥 Flirty Challenge** | High engagement | Strict "Dare" tasks; uses 'Flirty' question bank category. |
| **🎨 Draw & Guess** | Visual co-op | `DrawingUpdate` event broadcasts real-time base64 data. |
| **🤝 Co-op Task** | Teamwork focus | `CoopProgress` tracker requires *every* player to submit 'Complete'. |
| **🎭 Roleplay Lite** | Creative focus | Questioner defines a scenario; Active player responds in character. |
| **🎯 Random Match** | Safety focus | Strict **Opposite Gender** filtering via Redis queues. |
| **💞 Memory Meter** | Bond tracking | Increases `UserRelationship.closeness_score` by **+5** per success. |
| **🎲 Truth or Dare** | Classic party | Standard rotation of pre-defined and custom tasks. |

---

## 3. Real-Time WebSocket Events (`/ws/games/social/`)

| Event | Logic |
| :--- | :--- |
| `TurnAssigned` | Informs UI who is the "Doer" and who is the "Instructor". |
| `TaskCreated` | Broadcasts the specific challenge text and game mode. |
| `TimerStarted` | Triggers a 120s countdown in both UI and server-side task. |
| `CoopProgress` | Notifies the room how many players have finished the team task. |
| `DrawingUpdate` | High-frequency broadcast of canvas vector data. |

---

## 4. Scoring & Validation
- **XP Integration**: Successful transitions award **+20 XP** to the performer's `LevelProgress`.
- **Authoritative Validation**: For most modes, only the **Questioner** (not the performer) has the authority to click "Complete," preventing cheating.
- **Relationship Meter**: Interactions in Romantic/Memory modes directly feed the user-pair bonding score.

> [!TIP]
> **Expand Search**: If random matchmaking takes >45s, users can opt-in to bridge-match across gender queues to speed up game start.
