"""
PharmMCP Web UI - 流式输出版本

运行方式：
  终端1: python server.py --http
  终端2: python web_ui.py
  浏览器打开: http://127.0.0.1:7860
"""

import asyncio
import json
import os
import queue
import threading
from typing import Generator

import gradio as gr
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")
MODEL = os.getenv("LLM_MODEL")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")

SYSTEM_PROMPT = (
    "你是PharmMCP药物分子智能查询助手。"
    "用户会询问药物分子的相关信息，你需要调用合适的工具来获取数据并回答。\n\n"
    "使用建议：\n"
    "- 用户问某个分子基本信息 → search_molecule\n"
    "- 用户问物化性质 → get_molecule_properties（需要CID）\n"
    "- 用户问靶点/活性 → get_drug_targets\n"
    "- 用户问临床阶段/适应症 → get_clinical_info\n"
    "- 用户问相似化合物 → get_similar_molecules（需要SMILES）\n"
    "- 用户问类药性 → filter_by_druglikeness（需要CID）\n"
    "- 用户想快速了解全貌 → drug_screen（一步到位）\n\n"
    "- 用户问文献/论文/研究 → search_literature\n\n"
    "- 用户想对比两个药物 → drug_compare\n\n"
    "注意：如果用户只给了分子名没给CID/SMILES，先用search_molecule获取CID和SMILES，再调用其他工具。"
    "回答内容要专业准确，专业术语需附带通俗解释（例：logP（脂水分配系数）反映分子亲脂性）;数据需标注来源（如PubChem、ChEMBL等）;多工具结果需整合为连贯报告。所有回复均使用中文。"
)


def mcp_tools_to_openai_tools(mcp_tools):
    tools = []
    for tool in mcp_tools:
        tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            }
        })
    return tools


def _build_messages(message, history):
    """构建对话历史"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        if isinstance(msg, dict):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    return messages


async def _run_mcp_tools(message, history, status_queue):
    """异步执行MCP工具调用，结果通过queue返回"""
    openai_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    async with streamablehttp_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            openai_tools = mcp_tools_to_openai_tools(tools_result.tools)

            messages = _build_messages(message, history)

            for _ in range(5):
                response = openai_client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                    temperature=0.3,
                )

                choice = response.choices[0]
                assistant_msg = choice.message
                messages.append(assistant_msg.model_dump())

                if not assistant_msg.tool_calls:
                    return {"messages": messages, "final_response": assistant_msg.content}

                for tool_call in assistant_msg.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments)

                    # 推送工具调用状态
                    status_queue.put(f"🔧 调用工具: {func_name}...\n")

                    try:
                        result = await session.call_tool(func_name, func_args)
                        if result.content:
                            result_text = "\n".join(
                                item.text for item in result.content
                                if hasattr(item, "text")
                            )
                        else:
                            result_text = "工具返回为空"
                    except Exception as e:
                        result_text = f"工具调用失败: {e}"

                    status_queue.put(f"✅ {func_name} 完成\n")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result_text,
                    })

            return {"messages": messages}


def chat_fn(message, history) -> Generator:
    """Gradio流式聊天回调"""
    if not message or not message.strip():
        yield "请输入药物分子英文名，如 aspirin、ibuprofen"
        return

    status_queue = queue.Queue()
    result_container = {}

    def run_mcp():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _run_mcp_tools(message, history, status_queue)
            )
            result_container["result"] = result
        except Exception as e:
            result_container["error"] = str(e)
        finally:
            loop.close()
            status_queue.put(None)  # 结束信号

    thread = threading.Thread(target=run_mcp, daemon=True)
    thread.start()

    # 阶段1：显示工具调用进度
    output = ""
    while thread.is_alive() or not status_queue.empty():
        try:
            item = status_queue.get(timeout=0.1)
            if item is None:
                break
            output += item
            yield output
        except queue.Empty:
            continue

    thread.join(timeout=30)

    if "error" in result_container:
        yield output + f"\n❌ 查询失败: {result_container['error']}"
        return

    if "result" not in result_container:
        yield output + "\n❌ 查询超时，请重试"
        return

    # 阶段2：流式输出最终回复
    final = result_container.get("result", {}).get("final_response", "")
    if final:
        output += "\n🤖 "
        yield output
        for char in final:
            output += char
            yield output
    else:
        output += "\n❌ 未获取到有效回复"
        yield output


demo = gr.ChatInterface(
    fn=chat_fn,
    title="🧪 PharmMCP - 药物分子智能查询",
    description="输入药物分子名（如 aspirin、ibuprofen、瑞伐他汀），获取完整的分子简报",
    examples=["aspirin", "ibuprofen", "瑞伐他汀", "atorvastatin"],
)

if __name__ == "__main__":
    print("🧪 PharmMCP Web UI 启动中...")
    print("📱 浏览器打开: http://127.0.0.1:7860")
    demo.launch(server_name="127.0.0.1", server_port=7860)