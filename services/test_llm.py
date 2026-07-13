import asyncio

from services.llm_service import LLMService


async def main():
    llm = LLMService()

    response = await llm.chat()

    print(response)


if __name__ == "__main__":
    asyncio.run(main())