"""MCP client side (chapter 14): the orchestrator's server list.

Mantiene la lista de servidores a los que el orquestador se conecta al
arrancar — uno por cada agente que decide exponer. Ejecutado directamente,
se conecta a cada servidor y lista sus herramientas: la comprobacion de
que la capa MCP responde antes de conectarla al orquestador.
"""
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[1]

# Un servidor por agente expuesto; anade aqui los que decidas exponer
SERVERS = {
    "rag-personal": StdioServerParameters(
        command=sys.executable,
        args=[str(REPO_ROOT / "mcp_servers" / "rag_personal_server.py")],
    ),
}


async def list_server_tools(name: str, params: StdioServerParameters) -> None:
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"\n[{name}]")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")


async def main() -> None:
    print("Servidores MCP configurados:", ", ".join(SERVERS))
    for name, params in SERVERS.items():
        await list_server_tools(name, params)


if __name__ == "__main__":
    asyncio.run(main())
