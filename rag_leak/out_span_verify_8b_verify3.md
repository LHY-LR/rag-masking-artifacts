# 答案 span 复核探针（Qwen3-8B）

- 输入：`rag_leak/out_b8_full_k1/pilot_Qwen3-8B_substituted.jsonl`；条目 90
- 解析成功 81；改判 13

- **修复 10/22**（门槛 ≥10）：过
- **误伤 3/68**（门槛 ≤5）：过
- 被修复的题：['trivia-17', 'trivia-198', 'trivia-21', 'trivia-260', 'trivia-318', 'trivia-331', 'trivia-336', 'trivia-395', 'trivia-4', 'trivia-72']
- 被误伤的题：['trivia-223', 'trivia-274', 'trivia-430']

## 解析失败诊断

- 原因分布：{'no_explicit_verdict': 9}
- 原始输出样本（前 5 条）：
  - `trivia-12`: The marked value <<303>> is the year St. George died, which directly answers the question. Therefore, the answer is YES. The marked value <<303>> is the year St. George died, which directly answers th
  - `trivia-81`: The marked value <<451>> directly answers the question by providing the correct temperature referenced in the novel's title. The question asks for the specific number associated with Fahrenheit... and
  - `trivia-205`: The marked value <<14>> directly answers the question by stating the maximum number of golf clubs allowed in a player's bag under the rules of golf. The passage mentions that any number below 14 is ac
  - `trivia-340`: The marked occurrence "officially moved from Rio de Janeiro to Brasília" directly answers the question about the year the capital was moved. The year is implied in the context of the passage. The mark
  - `trivia-354`: The marked year 1997 is the year when the Goa'uld first appeared in the TV series Stargate SG-1, as the series was created that year and the Goa'uld are a central element of the show's storyline. The 

- `trivia-4` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-17` old=`4` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-21` old=`7` 管线=[23, 24] 模型=None（none=None）理由：
- `trivia-72` old=`18` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-198` old=`1491-1556` 管线=[119, 128] 模型=None（none=None）理由：
- `trivia-223` old=`210` 管线=[184, 187] 模型=None（none=None）理由：
- `trivia-260` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-274` old=`1768` 管线=[43, 47] 模型=None（none=None）理由：
- `trivia-318` old=`6` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-331` old=`19` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-336` old=`7` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-395` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-430` old=`1984` 管线=[260, 264] 模型=None（none=None）理由：
