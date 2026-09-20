# 答案 span 复核探针（Qwen3-8B）

- 输入：`rag_leak/out_b8_full_k1/pilot_Qwen3-8B_substituted.jsonl`；条目 90
- 解析成功 90；改判 18

- **修复 12/22**（门槛 ≥10）：过
- **误伤 6/68**（门槛 ≤5）：不过
- 被修复的题：['trivia-110', 'trivia-17', 'trivia-21', 'trivia-260', 'trivia-318', 'trivia-331', 'trivia-336', 'trivia-340', 'trivia-395', 'trivia-4', 'trivia-435', 'trivia-72']
- 被误伤的题：['trivia-274', 'trivia-300', 'trivia-386', 'trivia-402', 'trivia-407', 'trivia-430']

- `trivia-4` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-17` old=`4` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-21` old=`7` 管线=[23, 24] 模型=None（none=None）理由：
- `trivia-72` old=`18` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-110` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-260` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-274` old=`1768` 管线=[43, 47] 模型=None（none=None）理由：
- `trivia-300` old=`10` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-318` old=`6` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-331` old=`19` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-336` old=`7` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-340` old=`1960` 管线=[108, 112] 模型=None（none=None）理由：
- `trivia-386` old=`1987` 管线=[79, 83] 模型=None（none=None）理由：
- `trivia-395` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-402` old=`1907` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-407` old=`1947` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-430` old=`1984` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-435` old=`14` 管线=[9, 11] 模型=None（none=None）理由：
