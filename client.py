"""
PharmMCP Client - stdio模式

通过MCP协议连接本地Server，使用LLM决策调用工具。
支持多轮对话，自动工具调用。

运行方式：python client.py
"""

import asyncio
import json
import sys
from typing import Optional

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI

# 加载环境变量
load_dotenv()
import os

# LLM配置
API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL")
MODEL = os.getenv("LLM_MODEL")

# MCP Server配置
SERVER_PARAMS = StdioServerParameters(
    command="python",
    args=["server.py"],
)


def create_openai_client() -> OpenAI:
    """创建OpenAI兼容客户端"""
    if not API_KEY:
        print("❌ 未配置LLM_API_KEY，请在.env文件中填写")
        sys.exit(1)
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def mcp_tools_to_openai_tools(mcp_tools: list) -> list:
    """将MCP工具定义转换为OpenAI function calling格式"""
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
    """多轮对话主循环"""
    print("\n" + "=" * 50)
    print("PharmMCP 药物分子智能查询助手")
    print("输入分子名开始查询，输入 quit 退出")
    print("=" * 50 + "\n")

    # 对话历史
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

        # 多轮工具调用循环（LLM可能一次返回多个工具调用，也可能需要多轮）
        max_rounds = 10  # 防止无限循环
        for round_idx in range(max_rounds):
            # 调用LLM
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
                messages.pop()  # 移除失败的用户消息
                break

            choice = response.choices[0]
            assistant_msg = choice.message

            # 把assistant消息加入历史
            messages.append(assistant_msg.model_dump())

            # 如果没有工具调用，输出最终回复
            if not assistant_msg.tool_calls:
                print(f"\n🤖 PharmMCP: {assistant_msg.content}\n")
                break

            # 执行所有工具调用
            for tool_call in assistant_msg.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                call_id = tool_call.id

                print(f"  🔧 调用工具: {func_name}({func_args})")

                try:
                    # 通过MCP Session调用工具
                    result = await session.call_tool(func_name, func_args)

                    # 提取工具返回的文本内容
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

                # 把工具结果加入对话历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result_text,
                })


async def main():
    """主入口"""
    openai_client = create_openai_client()
    print(f"✅ LLM已连接: {BASE_URL} / {MODEL}")

    async with stdio_client(SERVER_PARAMS) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # 初始化MCP连接
            await session.initialize()
            print("✅ MCP Server已连接")

            # 获取工具列表
            tools_result = await session.list_tools()
            openai_tools = mcp_tools_to_openai_tools(tools_result.tools)
            print(f"✅ 已加载 {len(openai_tools)} 个工具: {[t['function']['name'] for t in openai_tools]}")

            # 进入对话循环
            await chat_loop(session, openai_client, openai_tools)


if __name__ == "__main__":
    asyncio.run(main())