"""
PharmMCP Client - Streamable HTTP模式

通过HTTP连接远程/云端MCP Server，使用LLM决策调用工具。
适合Server部署在远程服务器或Docker中的场景。

运行方式：先启动HTTP Server，再运行本客户端
  终端1: python server.py --http
  终端2: python client_http.py
"""

import asyncio
import json
import sys

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import OpenAI

# 加载环境变量
load_dotenv()
import os

# LLM配置
API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")
MODEL = os.getenv("LLM_MODEL")

# MCP Server HTTP地址
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")


def create_openai_client() -> OpenAI:
    if not API_KEY:
        print("❌ 未配置LLM_API_KEY，请在.env文件中填写")
        sys.exit(1)
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def mcp_tools_to_openai_tools(mcp_tools: list) -> list:
    openai_tools = []
    for tool in mcp_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            }
        })
    return openai_tools


async def chat_loop(session: ClientSession, openai_client: OpenAI, tools: list):
    print("\n" + "=" * 50)
    print("PharmMCP 药物分子智能查询助手 (HTTP模式)")
    print("输入分子名开始查询，输入 quit 退出")
    print("=" * 50 + "\n")

    messages = [
        {
            "role": "system",
            "content": (
                "你是PharmMCP药物分子智能查询助手，具备专业的药物分子知识和强大的数据查询能力，能精准高效地为用户提供药物分子相关信息。"
                "当用户询问药物分子的相关信息时，你要根据问题的类型调用合适的工具来获取数据并进行回答。\n\n"
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
            ),
        }
    ]

    while True:
        try:
            user_input = input("🧪 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        messages.append({"role": "user", "content": user_input})

        max_rounds = 10
        for round_idx in range(max_rounds):
            try:
                response = openai_client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.3,
                )
            except Exception as e:
                print(f"❌ LLM调用失败: {e}")
                messages.pop()
                break

            choice = response.choices[0]
            assistant_msg = choice.message
            messages.append(assistant_msg.model_dump())

            if not assistant_msg.tool_calls:
                print(f"\n🤖 PharmMCP: {assistant_msg.content}\n")
                break

            for tool_call in assistant_msg.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                call_id = tool_call.id

                print(f"  🔧 调用工具: {func_name}({func_args})")

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

                print(f"  ✅ 结果: {result_text[:100]}{'...' if len(result_text) > 100 else ''}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result_text,
                })


async def main():
    openai_client = create_openai_client()
    print(f"✅ LLM已连接: {BASE_URL} / {MODEL}")

    async with streamablehttp_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("✅ MCP Server已连接 (HTTP)")

            tools_result = await session.list_tools()
            openai_tools = mcp_tools_to_openai_tools(tools_result.tools)
            print(f"✅ 已加载 {len(openai_tools)} 个工具: {[t['function']['name'] for t in openai_tools]}")

            await chat_loop(session, openai_client, openai_tools)


if __name__ == "__main__":
    asyncio.run(main())