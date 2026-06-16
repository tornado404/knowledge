"""LangGraph Agent - 基于 langGraph 的多轮对话 RAG Agent"""

import os
import re
from typing import TypedDict, List, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END

# LangSmith Tracing
from langsmith import traceable

from .vectorstore import MilvusVectorStore
from .config import config
from .memory import estimate_tokens

# 启用 LangSmith tracing（如果配置了 API Key）
if config.langsmith_api_key:
    os.environ["LANGSMITH_API_KEY"] = config.langsmith_api_key
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = config.langsmith_project


# Graph State - 定义状态结构
class AgentState(TypedDict):
    """Agent 状态"""
    messages: List[dict]  # 对话消息历史
    context: str          # 检索到的上下文
    web_context: str      # 网页搜索到的上下文
    question: str         # 当前问题
    answer: str           # 最终答案
    route_decision: str   # 路由决策: "vector_only" | "web_only" | "both"
    sources: List[dict]   # 检索来源信息
    summary_context: str  # 压缩后的历史摘要上下文


def create_vectorstore_retriever(collection_name: str = None):
    """创建向量存储检索器"""
    vectorstore = MilvusVectorStore(collection_name=collection_name)
    vectorstore.load()
    return vectorstore


def retrieve_documents(vectorstore: MilvusVectorStore, query: str, k: int = 4):
    """检索相关文档"""
    docs = vectorstore.search(query, k=k)
    context_parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        content = doc.page_content
        context_parts.append(f"[文档{i}] ({source})\n{content}")
    return "\n\n".join(context_parts)


# ========== 路由正则规则 ==========
REGEX_ROUTES = [
    # web_only 关键词 - 实时性信息
    (r"今天|昨日|明日|本周|本月|今年|去年|明年", "web_only"),
    (r"新闻|最新|最近|现在|当前", "web_only"),
    (r"天气|温度|气温|降雨", "web_only"),
    (r"股价|股市|大盘|指数|涨停", "web_only"),
    (r"比赛|赛事|直播|实时", "web_only"),
    # both 关键词 - 既需要知识库又需要实时
    (r"对比|比较|区别|差异", "both"),
    (r"最新动态|最新消息", "both"),
    # vector_only 关键词 - 知识库内容
    (r"原理|概念|是什么|如何实现|怎么实现", "vector_only"),
    (r"架构|设计|代码|算法", "vector_only"),
]


def regex_route(question: str) -> Optional[str]:
    """正则预处理匹配"""
    for pattern, route in REGEX_ROUTES:
        if re.search(pattern, question):
            print(f"[route.pre] 正则命中 pattern='{pattern}' -> {route}")
            return route
    return None


def llm_route(question: str, pre_decision: Optional[str] = None) -> str:
    """LLM 判断路由"""
    llm = ChatAnthropic(model=config.anthropic_model or "MiniMax-M2.7")

    hint = f"[参考: 正则初步判定为 {pre_decision}]" if pre_decision else ""
    prompt = f"""你是一个查询分类助手。请分析用户问题，判断它最适合哪种检索方式。

问题：{question} {hint}

分类规则：
- "vector_only": 问题涉及知识库/内部文档内容，需要专业知识或历史数据
- "web_only": 问题涉及最新资讯、实时数据、新闻、天气、股价、突发事件等
- "both": 问题既涉及知识库内容又涉及最新信息，需要综合回答

请只输出一个分类标签：vector_only / web_only / both"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw_content = response.content

        if isinstance(raw_content, str):
            decision = raw_content.strip().lower()
        elif isinstance(raw_content, list):
            if raw_content:
                first_item = raw_content[0]
                if isinstance(first_item, dict):
                    decision = first_item.get("text", "").strip().lower()
                else:
                    decision = getattr(first_item, "text", "").strip().lower()
            else:
                decision = ""
        elif isinstance(raw_content, dict):
            decision = raw_content.get("text", "").strip().lower()
        else:
            decision = ""

        print(f"[route.llm] 原始响应: {raw_content}, 解析后: {decision}")

    except Exception as e:
        print(f"[route.llm] LLM 调用异常: {e}")
        decision = ""

    # 防御：空决策时使用正则预处理结果或默认值
    if not decision:
        if pre_decision:
            print(f"[route.llm] LLM 返回空，使用正则结果: {pre_decision}")
            decision = pre_decision
        else:
            print(f"[route.llm] LLM 返回空，使用默认: vector_only")
            decision = "vector_only"

    print(f"[route.llm] LLM 决策: {decision}")
    return decision


def post_route(question: str, pre: Optional[str], llm: str) -> str:
    """后处理：日志记录最终决策"""
    print(f"[route.post] 决策依据: 正则={pre}, LLM={llm}")
    print(f"[route.final] 最终路由: {llm}")
    return llm


# LangGraph Nodes
def route_node(state: AgentState) -> AgentState:
    """路由节点 - 正则预处理 + LLM 判断 + 后处理"""
    question = state["question"]

    # ========== 前处理日志 ==========
    print(f"\n[route] ===== 路由决策开始 =====")
    print(f"[route.pre] 问题: {question}")

    # ========== 正则预处理 ==========
    pre_decision = regex_route(question)

    # ========== LLM 判断 ==========
    llm_decision = llm_route(question, pre_decision)

    # ========== 后处理 ==========
    final_decision = post_route(question, pre_decision, llm_decision)

    # 确保决策结果是有效值
    if final_decision not in ("vector_only", "web_only", "both"):
        final_decision = "vector_only"

    print(f"[route] ===== 路由决策结束 =====\n")

    return {**state, "route_decision": final_decision}


def retrieve_node(state: AgentState) -> AgentState:
    """检索节点 - 从向量库检索相关文档"""
    vectorstore = create_vectorstore_retriever()
    question = state["question"]
    context = retrieve_documents(vectorstore, question, k=4)

    sources = []
    docs = vectorstore.search(question, k=4)
    for doc in docs:
        sources.append({
            "type": "vector",
            "source": doc.metadata.get("source", "unknown"),
            "content": doc.page_content[:200]
        })

    # 对于 "both" 路由，不清空 web_context（因为还没有）
    # 对于其他路由，清空 web_context
    route = state["route_decision"]
    if route != "both":
        return {**state, "context": context, "sources": sources}
    else:
        return {**state, "context": context, "sources": sources, "web_search_done": False}


def web_search_node(state: AgentState) -> AgentState:
    """网页搜索节点 - 使用 Tavily 进行网络搜索"""
    print(f"[web_search] 调用, route_decision={state.get('route_decision')}")

    try:
        from tavily import TavilyClient
    except ImportError:
        print("[web_search] tavily 未安装")
        return {**state, "web_context": "[未安装 tavily 包，无法进行网页搜索]", "web_search_done": True}

    # 如果已经有 web_context，说明执行过了，直接返回
    if state.get("web_context") and state.get("route_decision") == "both" and state.get("web_search_done"):
        print("[web_search] 已执行过，直接返回")
        return state

    if not config.tavily_api_key:
        print("[web_search] 未配置 API Key")
        return {**state, "web_context": "[未配置 Tavily API Key，无法进行网页搜索]", "web_search_done": True}

    try:
        print(f"[web_search] 开始搜索: {state['question']}")
        client = TavilyClient(api_key=config.tavily_api_key)
        results = client.search(query=state["question"], max_results=5, include_answer=True)
        print(f"[web_search] 搜索完成, 结果数: {len(results.get('results', []))}")

        context_parts = []
        sources = state.get("sources", [])

        for i, r in enumerate(results.get("results", []), 1):
            title = r.get("title", "Unknown")
            url = r.get("url", "")
            content = r.get("content", "")
            context_parts.append(f"[搜索结果{i}] {title}\n{content}\n来源: {url}")
            sources.append({
                "type": "web",
                "source": title,
                "url": url,
                "content": content[:200]
            })

        web_context = "\n\n".join(context_parts) if context_parts else "[未找到相关搜索结果]"
        print(f"[web_search] 返回 web_context: {web_context[:100]}...")
        return {**state, "web_context": web_context, "sources": sources, "web_search_done": True}

    except Exception as e:
        print(f"[web_search] 异常: {e}")
        return {**state, "web_context": f"[网页搜索失败: {str(e)}]", "web_search_done": True}


def merge_context_node(state: AgentState) -> AgentState:
    """合并上下文节点 - 合并向量检索和网页搜索的结果"""
    route = state["route_decision"]
    print(f"[merge] 调用, route={route}, context={state.get('context', '')[:50]}..., web_context={state.get('web_context', '')[:50]}...")

    if route == "vector_only":
        final_context = state["context"]
    elif route == "web_only":
        final_context = state.get("web_context", "") or state["context"]
    elif route == "both":
        final_context = f"""【知识库检索结果】
{state['context']}

【网络搜索结果】
{state.get('web_context', '')}"""
    else:
        # 降级：尝试向量检索
        final_context = state.get("context", "") or state.get("web_context", "")

    print(f"[merge] 最终 context: {final_context[:100]}...")
    return {**state, "context": final_context}


def generate_node(state: AgentState) -> AgentState:
    """生成节点 - 使用 LLM 生成回答"""
    model_name = config.anthropic_model or "MiniMax-M2.7"
    llm = ChatAnthropic(model=model_name)

    route = state["route_decision"]

    # 根据路由决策调整 system prompt
    if route == "web_only":
        system_content = """你是一个助手。请根据以下网络搜索结果回答用户的问题。
请注意：以下信息来自网络搜索，结果可能不准确，仅供参考。
如果搜索结果中没有相关内容，请如实告知。

"""
    elif route == "both":
        system_content = """你是一个知识库助手。请综合以下知识库检索和网络搜索结果回答用户的问题。
如果知识库和网络搜索都没有相关信息，请如实告知，不要编造答案。

"""
    else:
        system_content = """你是一个知识库助手。请根据以下参考信息回答用户的问题。
如果参考信息中没有相关内容，请如实告知，不要编造答案。

"""

    system_content += f"参考信息：\n{state['context']}"

    # 注入压缩后的历史摘要上下文
    summary_ctx = state.get("summary_context", "")
    if summary_ctx:
        system_content += f"\n\n对话历史摘要：\n{summary_ctx}"

    # 构建消息历史
    messages = []
    messages.append(SystemMessage(content=system_content))

    print(f"[generate] system_content: {system_content[:100]}...")

    # 基于 token 预算截断历史消息
    truncated_messages = _truncate_messages_by_token(state["messages"], DEFAULT_TOKEN_BUDGET)
    print(f"[generate] 原始消息数: {len(state['messages'])}, 截断后: {len(truncated_messages)}")

    # 添加历史消息
    has_messages = False
    for msg in truncated_messages:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
            has_messages = True
        else:
            messages.append(AIMessage(content=msg["content"]))

    # 确保至少有一条用户消息（某些 API 要求）
    if not has_messages:
        messages.append(HumanMessage(content=state["question"]))

    print(f"[generate] messages 数量: {len(messages)}")

    # 生成回答
    response = llm.invoke(messages)
    print(f"[generate] response: {response}")
    # 处理 response.content 的各种格式
    raw_answer = response.content
    if isinstance(raw_answer, str):
        answer = raw_answer
    elif isinstance(raw_answer, list):
        if raw_answer:
            first_item = raw_answer[0]
            if isinstance(first_item, dict):
                answer = first_item.get("text", "")
            else:
                answer = getattr(first_item, "text", "")
        else:
            answer = ""
    elif isinstance(raw_answer, dict):
        answer = raw_answer.get("text", "")
    else:
        answer = str(raw_answer)
    return {**state, "answer": answer}


# 条件边函数
def route_to_retrieval(state: AgentState) -> str:
    """根据路由决策确定下一步"""
    route = state["route_decision"]
    print(f"[route_to_retrieval] decision = {route}")
    if route == "vector_only":
        return "vector_only"
    elif route == "web_only":
        return "web_search"
    elif route == "both":
        return "both"
    else:
        return "vector_only"


def after_retrieval_or_websearch(state: AgentState) -> str:
    """检索或网页搜索后的下一步"""
    route = state["route_decision"]
    print(f"[after_retrieval_or_websearch] route={route}, web_search_done={state.get('web_search_done')}")

    if route == "both":
        # 两者都需要，先执行 retrieve，再执行 web_search，最后 merge
        if not state.get("web_search_done"):
            return "web_search"
        return "merge"
    else:
        return "merge"


# 创建 RAG Agent 图
def create_rag_agent_graph() -> StateGraph:
    """创建 RAG Agent 图"""
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("route", route_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("merge", merge_context_node)
    graph.add_node("generate", generate_node)

    # 设置入口点
    graph.set_entry_point("route")

    # 路由节点的条件边
    graph.add_conditional_edges(
        "route",
        route_to_retrieval,
        {
            "vector_only": "retrieve",
            "web_search": "web_search",
            "both": "retrieve",
        }
    )

    # retrieve 之后：对于 "both" 路由，决定是继续 web_search 还是 merge
    graph.add_conditional_edges(
        "retrieve",
        after_retrieval_or_websearch,
        {
            "web_search": "web_search",
            "merge": "merge",
        }
    )

    # web_search 之后：回到 after_retrieval_or_websearch 判断
    graph.add_conditional_edges(
        "web_search",
        after_retrieval_or_websearch,
        {
            "web_search": "web_search",
            "merge": "merge",
        }
    )

    # merge 之后到 generate
    graph.add_edge("merge", "generate")
    graph.add_edge("generate", END)

    return graph


def create_rag_agent():
    """创建可编译的 RAG Agent"""
    graph = create_rag_agent_graph()
    return graph.compile()


# 导出 graph 对象供 langgraph.json 使用
graph = create_rag_agent()


@traceable(run_type="chain")
def invoke_agent(question: str, history: List[dict] = None, summary_context: str = ""):
    """调用 agent 获取回答

    Args:
        question: 用户问题
        history: 对话历史 [{"role": "user"/"assistant", "content": "..."}]
        summary_context: 压缩后的历史摘要上下文

    Returns:
        回答文本
    """
    agent = create_rag_agent()

    initial_state = {
        "messages": history or [],
        "question": question,
        "context": "",
        "web_context": "",
        "answer": "",
        "route_decision": "",
        "sources": [],
        "summary_context": summary_context or "",
        "web_search_done": False,
    }

    result = agent.invoke(initial_state)
    return result["answer"]


async def stream_invoke_agent(question: str, history: List[dict] = None, summary_context: str = ""):
    """异步流式调用 agent，yield 增量 answer

    Args:
        question: 用户问题
        history: 对话历史 [{"role": "user"/"assistant", "content": "..."}]
        summary_context: 压缩后的历史摘要上下文

    Yields:
        增量回答文本
    """
    agent = create_rag_agent()

    initial_state = {
        "messages": history or [],
        "question": question,
        "context": "",
        "web_context": "",
        "answer": "",
        "route_decision": "",
        "sources": [],
        "summary_context": summary_context or "",
        "web_search_done": False,
    }

    previous_answer = ""
    async for event in agent.astream(initial_state, stream_mode="values"):
        current_answer = event.get("answer", "")
        if current_answer and current_answer != previous_answer:
            # yield 新增的部分
            new_content = current_answer[len(previous_answer):]
            if new_content:
                yield new_content
            previous_answer = current_answer


# ========== Token 控制常量 ==========
DEFAULT_TOKEN_BUDGET = 3000


def _truncate_messages_by_token(messages: List[dict], max_tokens: int = DEFAULT_TOKEN_BUDGET) -> List[dict]:
    """基于 token 预算截断消息历史"""
    if not messages:
        return messages

    budget = max_tokens * 0.8
    total_tokens = sum(estimate_tokens(m["content"]) for m in messages)
    if total_tokens <= budget:
        return messages

    # 从后向前保留（保留最新对话）
    truncated = []
    current_tokens = 0

    for msg in reversed(messages):
        msg_tokens = estimate_tokens(msg["content"])
        if current_tokens + msg_tokens <= budget:
            truncated.insert(0, msg)
            current_tokens += msg_tokens
        else:
            break

    # 如果截断后为空，至少保留最后一条
    if not truncated and messages:
        return [messages[-1]]

    return truncated

def invoke_multi_agent(question: str, history: List[dict] = None, session_id: str = None):
    """调用 Multi-Agent 系统处理问题

    Args:
        question: 用户问题
        history: 对话历史
        session_id: 会话 ID

    Returns:
        回答文本或任务 ID
    """
    import asyncio
    from .multi_agent import get_orchestrator

    async def _run():
        orchestrator = get_orchestrator()
        await orchestrator.initialize()

        sid = session_id or f"session_{id(question)}"
        state = await orchestrator.process_question(sid, question)

        # 简单等待完成（实际应该用更好的机制）
        for _ in range(30):
            await asyncio.sleep(1)
            result = await orchestrator.get_task_result(state.task_id)
            if result and result["status"] in ["done", "failed", "paused"]:
                break

        result = await orchestrator.get_task_result(state.task_id)
        await orchestrator.shutdown()
        return result

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(_run())
    return result
