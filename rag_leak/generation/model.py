"""模型后端（§0）：greedy/temp=0/唯一 prompt；四臂完全一致。

- HFGenerator：本地 transformers（Qwen3），量化参数显式传入。
  base 走 raw 续写（PROMPT_TEMPLATE*，Phase-B 起带 "A: The answer is" 前缀引导）；
  "-Instruct" 走 ChatML chat template（PROMPT_TEMPLATE_CHAT*，无前缀引导）。
- RemoteVLLMGenerator：32B 远程 vLLM（OpenAI 兼容接口），只切模型名。
- StubGenerator：mini 确定性测试桩（不联网、不加载模型），用"读证据/参数记忆"规则
  模拟四臂行为，仅用于验证管线机械正确性。
"""
from __future__ import annotations

from .. import config


def render_prompt(question: str, context: str | None) -> str:
    if context is None or context == "":
        return config.PROMPT_TEMPLATE_NOCTX.format(question=question)
    return config.PROMPT_TEMPLATE.format(context=context, question=question)


def is_instruct(model_name: str) -> bool:
    return str(model_name).endswith("-Instruct")


def render_chat_messages(question: str, context: str | None) -> list[dict]:
    """Phase C：Instruct 用 ChatML。user 消息措辞与 base 模板一致，仅去前缀引导。"""
    if context is None or context == "":
        content = config.PROMPT_TEMPLATE_CHAT_NOCTX.format(question=question)
    else:
        content = config.PROMPT_TEMPLATE_CHAT.format(context=context, question=question)
    return [{"role": "user", "content": content}]


# ---------------- 显存估算（§9 待确认 3：无卡环境无法实测，先给公式化估算） ----------------
def vram_estimate(params_b: float, bits: int, ctx_tokens: int,
                  n_layers: int = 36, hidden: int = 4096, kv_heads: int = 8,
                  head_dim: int = 128) -> dict:
    """粗估显存占用（GB），用于决定 8B×4K 的量化位数；真实值以压测为准。

    权重 ≈ 参数量 × bits/8；KV cache ≈ 2(k,v) × layers × ctx × kv_heads × head_dim × 2字节(fp16)；
    激活/框架开销预留 ~1.2GB。
    """
    w_gb = params_b * 1e9 * bits / 8 / 1e9
    kv_gb = 2 * n_layers * ctx_tokens * kv_heads * head_dim * 2 / 1e9
    overhead = 1.2
    return dict(weights_gb=round(w_gb, 2), kv_gb=round(kv_gb, 2),
                overhead_gb=overhead, total_gb=round(w_gb + kv_gb + overhead, 2),
                fits_8gb=(w_gb + kv_gb + overhead) <= 8.0)


def resolve_model_class(model_id: str):
    """按 checkpoint 的 `architectures` 解析模型类（跨世代兼容）。

    为什么不用 AutoModelForCausalLM：新版家族的 checkpoint 常常不是 `*ForCausalLM`。
    例如 Qwen3.5 全系列是 `Qwen3_5ForConditionalGeneration`（VL 结构），
    AutoModelForCausalLM 会解析到 `Qwen3_5ForCausalLM`（要求 Qwen3_5TextConfig），
    与本 checkpoint 的键结构不匹配 → 加载失败。

    策略：优先信任 `config.architectures[0]` 对应的类（`getattr` 动态取，**不硬编码表**，
    这样 transformers 升级新增架构时无需改本文件）；取不到再回落 AutoModelForCausalLM。
    返回 (类, 是否回落, architectures 列表)。
    """
    import transformers
    from transformers import AutoConfig, AutoModelForCausalLM
    cfg = AutoConfig.from_pretrained(model_id)
    archs = list(getattr(cfg, "architectures", None) or [])
    for name in archs:
        cls = getattr(transformers, name, None)
        if cls is not None:
            return cls, False, archs
    return AutoModelForCausalLM, True, archs


class HFGenerator:
    available = False

    def __init__(self, model_name: str, bits: int = 16, device: str = "cuda"):
        try:
            import torch  # 延迟重依赖
            from transformers import AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "HFGenerator 需要 torch+transformers（见 requirements.txt）；"
                "无卡环境请用 --generator stub 做接线冒烟。") from e
        from ..config import HF_MODEL_IDS
        self.model_name, self.device = model_name, device
        self.chat = is_instruct(model_name)
        # 支持两种写法：config 里登记的短名（如 'Qwen3-8B'）或完整 HF id（如 'Qwen/Qwen3.5-4B-Base'）。
        # 不含 '/' 又不在登记表里的名字几乎一定是笔误，给出明确报错（否则会被当成 HF 仓库名去解析，报错难懂）。
        if model_name in HF_MODEL_IDS:
            hf_id = HF_MODEL_IDS[model_name]
        elif "/" in model_name:
            hf_id = model_name
        else:
            raise ValueError(
                f"未知模型名 {model_name!r}：既不在 config.HF_MODEL_IDS 中，也不像完整 HF id。"
                f"请传已登记短名（如 'Qwen3-8B'）或完整 id（如 'Qwen/Qwen3.5-4B-Base'）。")
        self.hf_id = hf_id
        self.tok = AutoTokenizer.from_pretrained(hf_id)
        kw = dict(device_map=device)
        if bits == 4:
            from transformers import BitsAndBytesConfig
            # execution-fix: 默认 bnb_4bit_compute_dtype=float32 导致推理极慢（Qwen3 0.6B 单题>10s）；
            # 设为 float16 与输入 dtype 一致，推理速度恢复正常。语义不变（仅计算精度）。
            kw["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
        elif bits == 8:
            from transformers import BitsAndBytesConfig
            kw["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        else:
            kw["torch_dtype"] = torch.float16
        cls, fell_back, archs = resolve_model_class(hf_id)
        self.model_architectures, self.arch_fallback = archs, fell_back
        self.model = cls.from_pretrained(hf_id, **kw)
        self.available = True

    def generate_raw(self, prompt: str, max_new_tokens: int = 192) -> str:
        """按**原样 prompt** 生成：不套 §3 问答模板、不截首行、token 上限可调。

        为什么必须单开一个方法：`generate()` 的第一个位置参数语义是**问题**，它会被
        `render_prompt()` 套进冻结模板（`Q: … A: The answer is`）、返回值又只取
        `.split("\\n")[0]`、且 `max_new_tokens` 固定 64。任何"给一段指令、要完整 JSON 输出"
        的调用走 `generate()` 都必然拿不到 JSON —— C34 的 span 复核探针首次运行
        **解析成功 1/90** 就是这个原因（模型收到被包装成"问题"的长指令，然后按"最短答案"回了一句）。
        """
        inputs = self.tok(prompt, return_tensors="pt").to(self.model.device)
        out = self.model.generate(**inputs, max_new_tokens=max_new_tokens,
                                  do_sample=False, temperature=None, top_p=None)
        gen = out[0][inputs["input_ids"].shape[1]:]
        return self.tok.decode(gen, skip_special_tokens=True).strip()

    def generate(self, question: str, context: str | None, target_surface: str | None = None,
                 question_id: str = "", arm: str = "") -> str:
        if self.chat:
            msgs = render_chat_messages(question, context)
            # Phase C 修正：Qwen3-*-2507 是 thinking 模型，默认可能吐 <think> 推理块，
            # 会毁掉"最短答案"口径。显式关掉 thinking，让 instruct 直接给答案。
            # 模板不支持该 kwarg 时（TypeError/ValueError）回退无 kwarg 版本。
            try:
                prompt = self.tok.apply_chat_template(
                    msgs, tokenize=False, add_generation_prompt=True,
                    chat_template_kwargs={"enable_thinking": False})
            except (TypeError, ValueError):
                prompt = self.tok.apply_chat_template(
                    msgs, tokenize=False, add_generation_prompt=True)
        else:
            prompt = render_prompt(question, context)
        inputs = self.tok(prompt, return_tensors="pt").to(self.model.device)
        out = self.model.generate(**inputs, max_new_tokens=config.DECODE["max_new_tokens"],
                                  do_sample=False, temperature=None, top_p=None)
        gen = out[0][inputs["input_ids"].shape[1]:]
        return self.tok.decode(gen, skip_special_tokens=True).strip().split("\n")[0]


class RemoteVLLMGenerator:
    """32B：OpenAI 兼容 vLLM 服务；离线批处理，解码参数同样冻结。"""
    available = True

    def __init__(self, model_name: str, base_url: str, api_key: str = "EMPTY"):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name

    def generate(self, question: str, context: str | None, target_surface: str | None = None,
                 question_id: str = "", arm: str = "") -> str:
        prompt = render_prompt(question, context)
        resp = self.client.completions.create(
            model=self.model_name, prompt=prompt,
            max_tokens=config.DECODE["max_new_tokens"], temperature=0.0)
        return resp.choices[0].text.strip().split("\n")[0]


class StubGenerator:
    """mini 确定性测试桩。

    规则（显式模拟，便于检查管线符号方向）：
    - 开卷臂：上下文里若含目标答案串 → 输出目标（"纯靠证据"）；否则空；
    - 闭卷臂：题在 memorized 集合 → 输出【旧答案】（参数记忆）；
      其中 strong_memory 集合即使在 cb_sub 也仍答旧值（故意制造②的残留，演示闸门检出）。
    """
    available = True

    def __init__(self, memorized: set[str], strong_memory: set[str],
                 old_answer_of: dict[str, str]):
        self.memorized = set(memorized)
        self.strong = set(strong_memory)
        self.old_answer_of = dict(old_answer_of)

    def generate(self, question: str, context: str | None, target_surface: str | None = None,
                 question_id: str = "", arm: str = "") -> str:
        if context:  # 开卷：严格跟随上下文
            if target_surface and target_surface in context:
                return target_surface
            return ""
        # 闭卷
        if arm == "cb_sub":
            if question_id in self.strong:
                return self.old_answer_of.get(question_id, "")
            return ""
        if question_id in self.memorized:
            return self.old_answer_of.get(question_id, "")
        return ""
