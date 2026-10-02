# 小维响应耗时记录

单位 ms。total = 静音截断等待 + 联网/识别/回答全过程("说完 → 上屏")。

## 基线(优化前)

基线固件 = 提交「feat(pet): reliable serial logger, per-round timing, baseline」(只加了计时,未做任何优化)。

| 轮次 | trail | net | upload | asr | llm_conn | llm | total |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

中位 total:

## 优化后

(最终验收时填写)

## 基线 A(库化后,2026-10-02)

库化迁移完成(见 docs/superpowers/specs/2026-10-02-wiokit-library-design.md),时延未真机复测。
板子接上后跑 3 轮语音对话,把 `T:` 行各分项填在下表,与上一节基线对比(±5% 容差)。
另需目测确认 CJK 行缓冲渲染无视觉回归(气泡/待机提示/离线提示)。

| 轮次 | trail | net | upload | asr | llm_conn | llm | total |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

中位 total:
