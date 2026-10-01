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
