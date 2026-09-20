# Phase B Changelog（第三轮诊断 → 格式/解码/EM 修复）

## 触发原因
Phase A 目检（0.6B + 1.7B 各 12 题）确认 12/12 题为 A1（格式/解码/EM bug）：
- 1.7B 8/12 题输出元指令复读（"The answer should be in the context."），开卷仅 0.5%
- hotpot-1251 1.7B 实际输出 "The answer is Shane Meadows" 但 EM 判 0
- 0.6B 在 hotpot-12 答对（恰好年份格式匹配），证明"格式对了就能答对"

## 修改清单（3 处，均不改变语义）

### 1. config.py — prompt 加答案前缀引导
- `PROMPT_TEMPLATE` 末尾 `A:` → `A: The answer is`
- `PROMPT_TEMPLATE_NOCTX` 末尾 `A:` → `A: The answer is`
- 语义不变：仍然是"用最短答案回答，严格遵循上下文"；只是用前缀引导 base 模型直接输出答案而非元话语

### 2. config.py — max_new_tokens 32 → 64
- 避免长前缀答案（"The film in question is... The answer is X"）被截断
- 解码策略不变（greedy/temp=0/do_sample=False）

### 3. metrics/normalize.py — 新增 extract_answer()，EM 与顺从率均使用
- 新增 `extract_answer(raw)`：去掉行首常见答案前缀（the answer is / answer: / my answer is 等 8 种）
- `em_score()` / `em_any_alias()`：先 extract_answer 再 normalize 匹配
- `metrics/compliance.py` `classify_output()`：同样先 extract_answer
- 语义不变：仍是精确 EM（命中任一归一化别名）；只是更鲁棒地提取模型已输出的答案

## 未修改
- 构集逻辑（build_substituted / value_pool / proposal）：不受影响
- 检索逻辑（BM25 / distractor）：不受影响
- 四臂结构 / DiD 计算：不受影响
- 闸门阈值：不受影响

## 验证计划
1. `python -m rag_leak.selftest` — 管线机械正确性
2. `python -m rag_leak.run_pipeline --mode=mini` — mini 冒烟
3. `python -m rag_leak.check_round2 && python -m rag_leak.check_round3` — 回归
4. 0.6B + 1.7B pilot（--inspect 12）— 验证格式修复效果
5. 效果确认后重跑 8 格 grid
