import aiohttp
import io
import time
import os
import random
import json
from langdetect import detect
from gtts import gTTS
from urllib.parse import quote
from utils.config_loader import load_current_language, config
from openai import AsyncOpenAI
from duckduckgo_search import AsyncDDGS
from dotenv import load_dotenv

load_dotenv()

current_language = load_current_language()
internet_access = config.get("INTERNET_ACCESS", False)

_api_key = os.getenv("GROQ_API_KEY", "")
_client = AsyncOpenAI(
    base_url=config.get("API_BASE_URL", "https://api.groq.com/openai/v1/"),
    api_key=_api_key,
)


async def generate_response(instructions: str, history: list) -> str:
    messages = [
        {"role": "system", "name": "instructions", "content": instructions},
        *history,
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "searchtool",
                "description": "Searches the internet for current information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query.",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
    ]

    response = await _client.chat.completions.create(
        model=config.get("MODEL_ID", "mixtral-8x7b-32768"),
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    if tool_calls:
        available_functions = {"searchtool": duckduckgo_search}
        messages.append(response_message)

        for tool_call in tool_calls:
            func = available_functions.get(tool_call.function.name)
            if not func:
                continue
            args = json.loads(tool_call.function.arguments)
            result = await func(query=args.get("query", ""))
            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": result,
                }
            )

        second = await _client.chat.completions.create(
            model=config.get("MODEL_ID", "mixtral-8x7b-32768"),
            messages=messages,
        )
        return second.choices[0].message.content

    return response_message.content


async def duckduckgo_search(query: str) -> str:
    if not config.get("INTERNET_ACCESS", False):
        return "Internet access is currently disabled."

    blob = ""
    try:
        results = await AsyncDDGS(proxy=None).text(query, max_results=config.get("MAX_SEARCH_RESULTS", 4))
        for i, result in enumerate(results):
            blob += f"[{i}] {result['title']}\n{result['body']}\n\n"
    except Exception as e:
        blob = f"Search error: {e}"
    return blob


async def poly_image_gen(session: aiohttp.ClientSession, prompt: str) -> io.BytesIO:
    seed = random.randint(1, 100000)
    url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?seed={seed}"
    async with session.get(url) as response:
        data = await response.read()
    return io.BytesIO(data)


async def generate_image_prodia(
    prompt: str, model: str, sampler: str, seed: int, neg: str
) -> io.BytesIO:
    start = time.time()

    async def create_job():
        url = "https://api.prodia.com/generate"
        params = {
            "new": "true",
            "prompt": quote(prompt),
            "model": model,
            "steps": "100",
            "cfg": "9.5",
            "seed": str(seed),
            "sampler": sampler,
            "upscale": "True",
            "aspect_ratio": "square",
        }
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params=params) as r:
                data = await r.json()
                return data["job"]

    job_id = await create_job()
    headers = {"authority": "api.prodia.com", "accept": "*/*"}

    async with aiohttp.ClientSession() as session:
        while True:
            async with session.get(f"https://api.prodia.com/job/{job_id}", headers=headers) as r:
                data = await r.json()
                if data["status"] == "succeeded":
                    async with session.get(
                        f"https://images.prodia.xyz/{job_id}.png?download=1",
                        headers=headers,
                    ) as r2:
                        content = await r2.content.read()
                        print(f"[Lucky] Image ready in {time.time() - start:.1f}s")
                        return io.BytesIO(content)


async def text_to_speech(text: str) -> io.BytesIO:
    buf = io.BytesIO()
    lang = detect(text)
    tts = gTTS(text=text, lang=lang)
    tts.write_to_fp(buf)
    buf.seek(0)
    return buf

# Lucky Bot — Rewritten
