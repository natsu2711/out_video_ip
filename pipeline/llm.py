"""LLM 供应商链：强模型 → 免费 API → 本地 ollama → 规则兜底（管线永不因模型挂掉而阻塞）。

设计原则（拆自 video-talkcraft / lanshu 的稳定性范式）：
1. **小任务化**：一次调用只做一件事、只输出一个小 JSON——弱模型也能稳。
2. **schema 收窄**：所有 LLM 输出必须过 jsonschema + 业务校验；校验失败把「错误清单+原文」
   喂回修复（最多 max_repair 轮）——这就是"加一层解决不稳定"。
3. **链式降级**：PIPELINE_LLM_CHAIN 环境变量配置，默认 ollama 本地。任一环节失败自动降下一级。
4. **确定性**：temperature 固定低值；同输入同输出，方便复算与回归。

链语法（PIPELINE_LLM_CHAIN，"->" 分隔）:
  openai:BASE_URL|MODEL|KEY_ENV   任意 OpenAI 兼容端点（GLM/DeepSeek/OpenRouter/自建）
  ollama:MODEL                    本地 ollama（http://localhost:11434，免费）
  none                            直接失败（调用方走规则兜底）
例: export PIPELINE_LLM_CHAIN="openai:https://open.bigmodel.cn/api/paas/v4|glm-4.7|ZHIPU_KEY -> ollama:qwen3.5:9b -> none"
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Callable

from jsonschema import Draft7Validator


class LLMChainError(RuntimeError):
    """链上所有供应商都失败（调用方应走规则兜底）。"""


def _parse_chain() -> list[dict]:
    raw = os.environ.get("PIPELINE_LLM_CHAIN", "ollama:qwen3.5:9b-q4_K_M -> none")
    specs = []
    for part in raw.split("->"):
        part = part.strip()
        if not part:
            continue
        if part == "none":
            specs.append({"kind": "none"})
        elif part.startswith("ollama:"):
            specs.append({"kind": "ollama", "model": part[len("ollama:"):].strip(),
                          "base": os.environ.get("OLLAMA_BASE", "http://localhost:11434")})
        elif part.startswith("openai:"):
            # openai:BASE_URL|MODEL|KEY_ENV
            bits = part[len("openai:"):].split("|")
            specs.append({
                "kind": "openai",
                "base": bits[0].strip().rstrip("/"),
                "model": bits[1].strip() if len(bits) > 1 else "",
                "key_env": bits[2].strip() if len(bits) > 2 else "",
            })
        else:
            raise ValueError(f"PIPELINE_LLM_CHAIN 段无法解析: {part}")
    return specs


def _post_openai(spec: dict, messages: list[dict], temperature: float, timeout: int) -> str:
    key = os.environ.get(spec["key_env"], "") if spec.get("key_env") else ""
    req = urllib.request.Request(
        f"{spec['base']}/chat/completions",
        data=json.dumps({
            "model": spec["model"],
            "messages": messages,
            "temperature": temperature,
        }).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {key}"} if key else {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def _post_ollama(spec: dict, messages: list[dict], temperature: float, timeout: int) -> str:
    body = {
        "model": spec["model"],
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": 8192},
    }
    # 思考型模型（qwen3.5 等）：关 thinking 提速；老版 ollama 不认识该字段会报错，则去掉重试
    try:
        req = urllib.request.Request(
            f"{spec['base']}/api/chat",
            data=json.dumps({**body, "think": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data["message"]["content"]
    except urllib.error.HTTPError as e:
        if e.code not in (400, 404, 422):
            raise
        req = urllib.request.Request(
            f"{spec['base']}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data["message"]["content"]


def complete(prompt: str, system: str | None = None, temperature: float = 0.2,
             timeout: int = 180) -> tuple[str, str]:
    """沿链调用，返回 (文本, 供应商标签)。全挂抛 LLMChainError。"""
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    errors = []
    for spec in _parse_chain():
        if spec["kind"] == "none":
            break
        try:
            if spec["kind"] == "openai":
                out = _post_openai(spec, messages, temperature, timeout)
            else:
                out = _post_ollama(spec, messages, temperature, timeout)
            if out and out.strip():
                return out, f"{spec['kind']}:{spec.get('model', '')}"
            errors.append(f"{spec['kind']}: 空响应")
        except Exception as e:  # noqa: BLE001 任何供应商错误都降级
            errors.append(f"{spec['kind']}{spec.get('model', '')}: {e}")
    raise LLMChainError("；".join(errors) or "空链")


def extract_json(text: str):
    """从 LLM 文本里稳出 JSON：容忍 ```json 围栏、前后废话、尾逗号（弱模型常见病）。"""
    text = text.strip()
    # 1) 剥围栏
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # 2) 截第一个 { 或 [ 到最后一个 } 或 ]
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts:
        raise ValueError("响应中无 JSON")
    s = min(starts)
    e = max(text.rfind("}"), text.rfind("]"))
    raw = text[s:e + 1]
    # 3) 去尾逗号
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return json.loads(raw)


def complete_json(prompt: str, schema: dict | None = None,
                  business_check: Callable[[dict], list[str]] | None = None,
                  system: str | None = None, max_repair: int = 2,
                  temperature: float = 0.2) -> tuple[dict, str]:
    """complete + JSON 稳出 + schema/业务校验 + 错误喂回修复循环。

    返回 (对象, 供应商标签)。修复循环耗尽仍失败 → LLMChainError（调用方走 fallback）。
    """
    v = Draft7Validator(schema) if schema else None
    messages = ([{"role": "system", "content": system}] if system else [])
    last_provider = "?"
    for attempt in range(max_repair + 1):
        p = prompt if attempt == 0 else (
            f"{prompt}\n\n你上次的输出未通过校验，错误清单：\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\n只输出修正后的 JSON，不要任何解释。"
        )
        text, last_provider = complete(p, system=system, temperature=temperature)
        messages = messages + [{"role": "user", "content": p}, {"role": "assistant", "content": text}]
        try:
            obj = extract_json(text)
        except (ValueError, json.JSONDecodeError) as e:
            errors = [f"JSON 解析失败: {e}"]
            continue
        if v is not None:
            errors = [f"{'/'.join(map(str, x.path))}: {x.message}" for x in v.iter_errors(obj)]
            if errors:
                continue
        if business_check is not None:
            errors = business_check(obj)
            if errors:
                continue
        return obj, last_provider
    raise LLMChainError(f"修复 {max_repair} 轮后仍不合法: {errors}")


def chain_label() -> str:
    return os.environ.get("PIPELINE_LLM_CHAIN", "ollama:qwen3.5:9b-q4_K_M -> none")
