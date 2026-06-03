# RL Bot

Behavior-cloning + PPO reinforcement learning training pipeline for Cthulhu Wars faction bots.

User-facing docs (vision, plan, tasks, rollback log) live at:
`My Drive/Personal/Games/Cthulhu Wars/admin/Reinforced Learning Bot/`

## Layout

```
rl-bot/
├── encoder/              state encoder: replay state → fixed feature tensor
├── extractor/            replay → (state, action, reward, tag) tuples
├── training/             BC trainer, PPO trainer, reward function, sim worker pool
├── export/               PyTorch → ONNX export
├── orchestrator/         FastAPI server, exposes /train /status /deploy to admin console
├── scala-inference/      Scala-side ONNX loader (called by faction bots)
└── configs/
    ├── reward_weights.yaml         defaults for all factions
    ├── training_done_bars.yaml     per-faction stop criteria
    └── faction_overrides/          per-faction reward overrides (Bubastis, etc.)
```

## Status

- P0 (discovery): done. Docs in Drive.
- P1 (scaffolding): in progress. Directory + configs landed. State schema, SimRunner emit-decisions hook pending.

See `My Drive/.../admin/Reinforced Learning Bot/RL Bot — Claude Tasks.docx` for full status.
