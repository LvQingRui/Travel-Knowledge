import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.config import Settings
from app.processor.retriever import multi_path_retrieve
from app.utils.llm_client import build_citations, chat_complete

logger = logging.getLogger("travel.qa")


class QAState(TypedDict, total=False):
    query: str
    region: str | None
    content_type: str | None
    scenic_name: str | None
    top_k: int
    history: list[dict]
    contexts: list[dict]
    recall_info: dict
    citations: list[dict]
    answer: str


def _retrieve_node(state: QAState, settings: Settings) -> dict:
    logger.info("LangGraph: 检索节点 query=%r", state["query"])
    hits, recall_info = multi_path_retrieve(
        settings,
        query=state["query"],
        top_k=state.get("top_k"),
        region=state.get("region"),
        content_type=state.get("content_type"),
        scenic_name=state.get("scenic_name"),
    )
    return {
        "contexts": hits,
        "recall_info": recall_info,
        "citations": build_citations(hits),
    }


def _generate_node(state: QAState, settings: Settings) -> dict:
    logger.info(
        "LangGraph: 生成节点, 上下文 %s 条, 历史 %s 轮",
        len(state.get("contexts", [])),
        len(state.get("history", [])) // 2,
    )
    answer = chat_complete(
        query=state["query"],
        contexts=state.get("contexts", []),
        settings=settings,
        history=state.get("history"),
    )
    return {"answer": answer}


def build_qa_graph(settings: Settings):
    workflow = StateGraph(QAState)

    workflow.add_node("retrieve", lambda state: _retrieve_node(state, settings))
    workflow.add_node("generate", lambda state: _generate_node(state, settings))
    workflow.add_edge(START, "retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()


def run_qa(
    settings: Settings,
    query: str,
    region: str | None = None,
    content_type: str | None = None,
    scenic_name: str | None = None,
    top_k: int | None = None,
    history: list[dict] | None = None,
) -> QAState:
    graph = build_qa_graph(settings)
    result = graph.invoke(
        {
            "query": query,
            "region": region,
            "content_type": content_type,
            "scenic_name": scenic_name,
            "top_k": top_k,
            "history": history or [],
        }
    )
    return result
