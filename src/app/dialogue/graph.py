"""LangGraph：START → safety → refuse | react → generate。"""

from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.character import CharacterProfile, CharacterRepository
from app.character.react import ReactPolicy
from app.dialogue.generate import invoke_generation
from app.dialogue.state import DialogueState, HistoryMessage
from app.llm import ChatModelFactory
from app.safety import SafetyPolicy


def build_model_messages(
    character: CharacterProfile,
    history: list[HistoryMessage],
    user_text: str,
    react_hint: str = "",
) -> list[BaseMessage]:
    """拼 System + 历史 + 本轮用户句。流式和非流式都走这里。"""
    messages: list[BaseMessage] = [SystemMessage(content=character.system_prompt())]
    # 呼唤口吻只这一轮生效，不写进人设正文
    if react_hint:
        messages.append(
            SystemMessage(
                content=f"这一轮用户在喊你。先用这句口吻应一声，再接他后头的话。不要解释规则：{react_hint}"
            )
        )
    for item in history:
        if item["role"] == "assistant":
            messages.append(AIMessage(content=item["content"]))
        else:
            messages.append(HumanMessage(content=item["content"]))
    messages.append(HumanMessage(content=user_text))
    return messages


def build_dialogue_graph(
    characters: CharacterRepository,
    llm_factory: ChatModelFactory,
    safety: SafetyPolicy,
    react: ReactPolicy | None = None,
):
    reactions = react or ReactPolicy()

    def safety_node(state: DialogueState) -> dict:
        decision = safety.evaluate(state.user_text)
        return {
            "safety_action": decision.action,
            "safety_code": decision.code,
        }

    def route_after_safety(state: DialogueState) -> str:
        return "refuse" if state.safety_action == "refuse" else "react"

    def refuse_node(state: DialogueState) -> dict:
        character = characters.get(state.character_id)
        return {"assistant_text": character.refusal_text(state.safety_code)}

    def react_node(state: DialogueState) -> dict:
        character = characters.get(state.character_id)
        salt = f"{state.conversation_id}:{len(state.history)}"
        decision = reactions.evaluate(character, state.user_text, salt=salt)
        if decision.action == "reply":
            return {
                "react_action": decision.action,
                "react_code": decision.code,
                "react_hint": "",
                "assistant_text": decision.text,
            }
        return {
            "react_action": decision.action,
            "react_code": decision.code,
            "react_hint": decision.text,
        }

    def route_after_react(state: DialogueState) -> str:
        return "done" if state.assistant_text else "generate"

    def generate_node(state: DialogueState, config: RunnableConfig) -> dict:
        character = characters.get(state.character_id)
        messages = build_model_messages(
            character,
            state.history,
            state.user_text,
            react_hint=state.react_hint,
        )
        # 把父 span 的 metadata 传下去，LangSmith 才能把 LLM 调用挂到同一轮
        generation = invoke_generation(llm_factory, character, messages, config)
        return {
            "assistant_text": generation.text,
            "model_used": generation.model,
            "degraded": generation.degraded,
        }

    graph = StateGraph(DialogueState)
    graph.add_node("safety", safety_node)
    graph.add_node("react", react_node)
    graph.add_node("generate", generate_node)
    graph.add_node("refuse", refuse_node)
    graph.add_edge(START, "safety")
    graph.add_conditional_edges(
        "safety",
        route_after_safety,
        {"react": "react", "refuse": "refuse"},
    )
    graph.add_conditional_edges(
        "react",
        route_after_react,
        {"generate": "generate", "done": END},
    )
    graph.add_edge("generate", END)
    graph.add_edge("refuse", END)
    return graph.compile()  # 进程内复用，不要每个请求 compile
