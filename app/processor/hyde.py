import logging

import dashscope
from dashscope import Generation

from app.config import Settings

logger = logging.getLogger("travel.hyde")

HYDE_PROMPT = """你是一个旅游攻略文档撰写助手。
请根据用户的旅游相关问题，写一段可能出现在旅游攻略 Markdown 文档中的假设性段落。
要求：100-200字，包含具体景点名、地区、实用信息，只输出段落正文，不要解释。"""


class HyDEError(Exception):
    pass


def generate_hyde_document(query: str, settings: Settings) -> str:
    if not settings.dashscope_api_key:
        raise HyDEError("未配置 DASHSCOPE_API_KEY，无法生成 HyDE 文档")

    dashscope.api_key = settings.dashscope_api_key
    response = Generation.call(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": HYDE_PROMPT},
            {"role": "user", "content": f"问题：{query}"},
        ],
        result_format="message",
        max_tokens=300,
    )

    if response.status_code != 200:
        raise HyDEError(f"HyDE 生成失败: {response.code} - {response.message}")

    content = response.output.choices[0].message.content.strip()
    logger.info("HyDE 生成完成: %s...", content[:60])
    return content
