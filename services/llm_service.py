from config import OPENAI_API_KEY, OPENAI_MODEL
from openai import AsyncOpenAI


class LLMService:
    def __init__(self):
        self.model = OPENAI_MODEL
        self.client = AsyncOpenAI(
            api_key=OPENAI_API_KEY
        )

    async def chat(
        self,
        messages: list,
        tools: list | None = None,
    ):
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
        )

        return response