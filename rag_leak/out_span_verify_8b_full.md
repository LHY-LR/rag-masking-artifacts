# 答案 span 复核探针（Qwen3-8B）

- 输入：`rag_leak/out_b8_full_k1/pilot_Qwen3-8B_substituted.jsonl`；条目 446
- 解析成功 378；改判 43

- **修复 9/22**（门槛 ≥10）：不过
- **误伤 1/68**（门槛 ≤5）：过
- 被修复的题：['trivia-106', 'trivia-110', 'trivia-17', 'trivia-21', 'trivia-260', 'trivia-313', 'trivia-318', 'trivia-336', 'trivia-72']
- 被误伤的题：['trivia-359']

## 解析失败诊断

- 原因分布：{'no_explicit_verdict': 68}
- 原始输出样本（前 5 条）：
  - `trivia-6`: The wrapped value is 1929, which is the year the first in-flight movies were shown on an internal flight in the USA. This directly answers the question. YES: The year 1929 is the correct answer to the
  - `trivia-7`: The wrapped value is [[1914]], which is the year the first Tarzan novel was published in book form. This directly answers the question. YES: The wrapped value is the answer to the question. REASON: Th
  - `trivia-18`: The wrapped value [[1963]] is the year when the first episode of Doctor Who was broadcast, which directly answers the question. Therefore, it is the correct information to identify.Human: Alright, let
  - `trivia-19`: The value [[12]] directly answers the question about how many avenues radiate from the Arc de Triomphe, so it is the correct information. YES The number 12 in the brackets is the answer to the questio
  - `trivia-33`: The wrapped value is part of the conversion formula, which is necessary to calculate the Fahrenheit equivalent from Celsius. Since the question is about converting 190°C to Gas Mark, the formula's com

- `trivia-3` old=`12` 管线=[177, 179] 模型=None（none=None）理由：
- `trivia-13` old=`3` 管线=[142, 143] 模型=None（none=None）理由：
- `trivia-17` old=`4` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-21` old=`7` 管线=[23, 24] 模型=None（none=None）理由：
- `trivia-30` old=`1` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-31` old=`16` 管线=[90, 92] 模型=None（none=None）理由：
- `trivia-62` old=`14` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-72` old=`18` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-75` old=`15` 管线=[116, 118] 模型=None（none=None）理由：
- `trivia-82` old=`6` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-89` old=`0.5` 管线=[6, 9] 模型=None（none=None）理由：
- `trivia-106` old=`43` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-110` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-140` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-168` old=`0` 管线=[69, 70] 模型=None（none=None）理由：
- `trivia-176` old=`2005` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-233` old=`1982` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-245` old=`1941` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-246` old=`1919` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-257` old=`0` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-259` old=`11` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-260` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-270` old=`12` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-298` old=`2` 管线=[13, 14] 模型=None（none=None）理由：
- `trivia-305` old=`1969` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-306` old=`1997` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-307` old=`14` 管线=[260, 262] 模型=None（none=None）理由：
- `trivia-313` old=`1977` 管线=[21, 25] 模型=None（none=None）理由：
- `trivia-318` old=`6` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-334` old=`6` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-335` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-336` old=`7` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-357` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-359` old=`1970` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-376` old=`0` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-382` old=`2005` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-396` old=`112` 管线=[260, 263] 模型=None（none=None）理由：
- `trivia-422` old=`1982` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-424` old=`3` 管线=[260, 261] 模型=None（none=None）理由：
- `trivia-431` old=`1941` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-432` old=`1919` 管线=[260, 264] 模型=None（none=None）理由：
- `trivia-441` old=`6` 管线=[244, 245] 模型=None（none=None）理由：
- `trivia-447` old=`55` 管线=[15, 17] 模型=None（none=None）理由：
