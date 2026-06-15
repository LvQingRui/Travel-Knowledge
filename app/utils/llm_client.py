import json
import logging
from typing import AsyncIterator

import httpx

from app.config import Settings

logger = logging.getLogger("travel.llm")

SYSTEM_PROMPT = """你是旅游知识库智能助手。请基于提供的参考资料回答用户的旅游相关问题。

要求：
1. 只根据参考资料回答，不要编造不存在的信息
2. 回答要条理清晰，包含实用建议和注意事项
3. 引用资料时使用 [1][2] 等编号标注
4. 如果参考资料不足以回答，请明确告知用户
5. 使用中文回答"""


class LLMError(Exception):
    pass


def _build_messages(query: str, contexts: list[dict], history: list[dict] | None = None) -> list[dict]:
    context_text = _format_contexts(contexts)
    user_content = f"""参考资料：
{context_text}

用户问题：{query}"""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_content})
    return messages


def _format_contexts(contexts: list[dict]) -> str:
    if not contexts:
        return "（暂无相关参考资料）"
    parts = []
    for i, hit in enumerate(contexts, 1):
        source = hit.get("source_filename") or hit.get("recall_source") or "未知"
        region = hit.get("region") or "未知"
        parts.append(f"[{i}] 来源: {source} | 地区: {region}\n{hit.get('content', '')}")
    return "\n\n".join(parts)


def build_citations(contexts: list[dict]) -> list[dict]:
    citations = []
    for i, hit in enumerate(contexts, 1):
        citations.append(
            {
                "index": i,
                "source_filename": hit.get("source_filename", ""),
                "source_path": hit.get("source_path", ""),
                "region": hit.get("region", ""),
                "content_type": hit.get("content_type", ""),
                "recall_source": hit.get("recall_source", ""),
                "snippet": (hit.get("content") or "")[:200],
            }
        )
    return citations


def _get_api_config(settings: Settings) -> tuple[str, str, str]:
    if settings.llm_provider == "deepseek":
        if not settings.deepseek_api_key:
            raise LLMError("未配置 DEEPSEEK_API_KEY")
        return (
            settings.deepseek_base_url.rstrip("/"),
            settings.deepseek_api_key,
            settings.chat_model,
        )
    if not settings.dashscope_api_key:
        raise LLMError("未配置 DASHSCOPE_API_KEY")
    return (
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        settings.dashscope_api_key,
        settings.chat_model,
    )


def chat_complete(
    query: str,
    contexts: list[dict],
    settings: Settings,
    history: list[dict] | None = None,
) -> str:
    base_url, api_key, model = _get_api_config(settings)
    messages = _build_messages(query, contexts, history)

    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages, "stream": False},
        )
        if response.status_code != 200:
            raise LLMError(f"LLM 调用失败: {response.status_code} {response.text}")
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def chat_stream(
    query: str,
    contexts: list[dict],
    settings: Settings,
    history: list[dict] | None = None,
) -> AsyncIterator[str]:
    base_url, api_key, model = _get_api_config(settings)
    messages = _build_messages(query, contexts, history)

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages, "stream": True},
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                raise LLMError(f"LLM 流式调用失败: {response.status_code} {body.decode()}")

            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    logger.debug("跳过无法解析的流式片段: %s", payload)
