import os
import discord
import aiosqlite
from discord.ext import commands, tasks
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
from datetime import datetime, timezone, timedelta
import asyncio
from typing import List, Dict, Optional
from discord import app_commands
import random
import aiohttp
import logging
import io
from PIL import Image

logger = logging.getLogger('discord')
logger.setLevel(logging.WARNING)

fallback_questions = {
    "history": [{"question": "Who was the first President of the United States?", "answer": "George Washington"},
                {"question": "In what year did the Titanic sink?", "answer": "1912"}],
    "science": [{"question": "What gas makes up most of Earth's atmosphere?", "answer": "Nitrogen"},
                {"question": "What is the chemical symbol for gold?", "answer": "Au"}],
    "general": [{"question": "What is the smallest country in the world?", "answer": "Vatican City"},
                {"question": "What is the hardest natural substance on Earth?", "answer": "Diamond"}],
}
categories = ["history", "science", "general"]


class TriviaScore:
    def __init__(self, bot):
        self.bot = bot

    async def find_one_and_update(self, query, update, upsert=True):
        user_id = query["userId"]
        username = update.get("username", "Unknown")
        score_inc = update["$inc"]["score"]
        games_played_inc = update["$inc"]["gamesPlayed"]
        history_entry = update["$push"]["history"]
        async with self.bot.db.execute("SELECT score, games_played, history FROM trivia_scores WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
        if result:
            current_score, games_played, history_str = result
            history = eval(history_str) if history_str else []
            new_score = current_score + score_inc
            new_games_played = games_played + games_played_inc
            history.append(history_entry)
        else:
            new_score, new_games_played, history = score_inc, games_played_inc, [history_entry]
        await self.bot.db.execute("INSERT OR REPLACE INTO trivia_scores (user_id, username, score, games_played, history) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, new_score, new_games_played, str(history)))
        await self.bot.db.commit()
        return {"score": new_score, "gamesPlayed": new_games_played, "history": history}

    async def find(self):
        async with self.bot.db.execute("SELECT user_id, username, score, games_played, history FROM trivia_scores ORDER BY score DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()
            return [{"userId": r[0], "username": r[1], "score": r[2], "gamesPlayed": r[3], "history": eval(r[4]) if r[4] else []} for r in rows]

    async def find_one(self, query):
        async with self.bot.db.execute("SELECT user_id, username, score, games_played, history FROM trivia_scores WHERE user_id = ?", (query["userId"],)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"userId": row[0], "username": row[1], "score": row[2], "gamesPlayed": row[3], "history": eval(row[4]) if row[4] else []}
            return None


class PersonalityModal(discord.ui.Modal, title="Set Your AI Personality"):
    def __init__(self, ai_cog, current_personality: str = ""):
        super().__init__()
        self.ai_cog = ai_cog
        self.personality_input = discord.ui.TextInput(
            label="Your AI Personality",
            placeholder="Describe how you want Lucky Bot to respond to you...",
            default=current_personality if current_personality.strip() else "You are Lucky Bot, a helpful Discord bot assistant. Be friendly and helpful.",
            style=discord.TextStyle.paragraph, max_length=2000, required=True
        )
        self.add_item(self.personality_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id, guild_id = interaction.user.id, interaction.guild.id
        personality = self.personality_input.value.strip()
        try:
            await self.ai_cog.bot.db.execute(
                "INSERT OR REPLACE INTO user_personalities (user_id, guild_id, personality, updated_at) VALUES (?, ?, ?, ?)",
                (user_id, guild_id, personality, datetime.now(timezone.utc)))
            await self.ai_cog.bot.db.commit()
            embed = discord.Embed(title="✨ Personality Set", description="Your AI personality has been updated!", color=0x57F287, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Your Personality", value=personality[:1024], inline=False)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"🃏 Failed to save personality: {e}", ephemeral=True)


class TriviaAnswerView(discord.ui.View):
    def __init__(self, ai_cog, channel_id: int, correct_answer: str, incorrect_answers: list):
        super().__init__(timeout=30)
        self.ai_cog = ai_cog
        self.channel_id = channel_id
        self.correct_answer = correct_answer
        all_answers = [correct_answer] + incorrect_answers
        random.shuffle(all_answers)
        for i, answer in enumerate(all_answers[:4]):
            button = discord.ui.Button(label=answer[:80], style=discord.ButtonStyle.primary, custom_id=f"answer_{i}")
            button.callback = self.create_answer_callback(answer)
            self.add_item(button)

    def create_answer_callback(self, answer: str):
        async def callback(interaction: discord.Interaction):
            await self.ai_cog.handle_trivia_answer(interaction, self.channel_id, answer)
        return callback


class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gemini_api_key = os.getenv("GOOGLE_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.chatbot_enabled = {}
        self.chatbot_channels = {}
        self.conversation_history = {}
        self.trivia_scores = TriviaScore(bot)
        self.active_games = {}
        self.roleplay_channels = {}
        self.question_cache = {cat: [] for cat in categories}
        asyncio.create_task(self._delayed_init())

    async def cog_load(self):
        pass

    @commands.group(name="ai", invoke_without_command=True, description="AI chatbot and utility commands")
    async def ai(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    async def _create_tables(self):
        try:
            if not hasattr(self.bot, 'db') or self.bot.db is None:
                db_path = "db/ai_data.db"
                if os.path.exists(db_path):
                    try:
                        test_conn = await aiosqlite.connect(db_path)
                        await test_conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
                        await test_conn.close()
                    except Exception:
                        os.remove(db_path)
                self.bot.db = await aiosqlite.connect(db_path)

            await self.bot.db.execute("""CREATE TABLE IF NOT EXISTS chatbot_settings (guild_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 0, chatbot_channel_id INTEGER)""")
            await self.bot.db.execute("""CREATE TABLE IF NOT EXISTS chatbot_history (user_id INTEGER, guild_id INTEGER, message TEXT, response TEXT, timestamp TEXT, PRIMARY KEY (user_id, guild_id, timestamp))""")
            await self.bot.db.execute("""CREATE TABLE IF NOT EXISTS conversation_memory (user_id INTEGER, guild_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, guild_id, timestamp))""")
            await self.bot.db.execute("""CREATE TABLE IF NOT EXISTS trivia_scores (user_id INTEGER PRIMARY KEY, username TEXT, score INTEGER DEFAULT 0, games_played INTEGER DEFAULT 0, history TEXT)""")
            await self.bot.db.execute("""CREATE TABLE IF NOT EXISTS user_personalities (user_id INTEGER, guild_id INTEGER, personality TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, guild_id))""")
            await self.bot.db.commit()
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")

    async def _delayed_init(self):
        await self.bot.wait_until_ready()
        await self._create_tables()
        await self._load_data()

    async def _load_data(self):
        try:
            if not hasattr(self.bot, 'db') or self.bot.db is None:
                db_path = "db/ai_data.db"
                if not os.path.exists(db_path):
                    return
                self.bot.db = await aiosqlite.connect(db_path)
            async with self.bot.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chatbot_settings';") as cursor:
                if await cursor.fetchone():
                    async with self.bot.db.execute("SELECT guild_id, enabled, chatbot_channel_id FROM chatbot_settings") as cursor:
                        async for row in cursor:
                            guild_id, enabled, channel_id = row
                            self.chatbot_enabled[guild_id] = bool(enabled)
                            self.chatbot_channels[guild_id] = channel_id
        except Exception as e:
            logger.error(f"Error loading chatbot settings: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        guild_id, channel_id = message.guild.id, message.channel.id
        if self.chatbot_enabled.get(guild_id, False) and self.chatbot_channels.get(guild_id) == channel_id:
            content = message.content.strip()
            if not content:
                return
            user_id = message.author.id
            await self._cleanup_old_conversations()
            await self._store_conversation_message(user_id, guild_id, "user", content)
            history = await self._get_conversation_history(user_id, guild_id, limit=30)
            async with message.channel.typing():
                response = await self._get_response(content, history, guild_id, user_id)
                await message.reply(response, mention_author=True, allowed_mentions=discord.AllowedMentions(users=True))
                await self._store_conversation_message(user_id, guild_id, "assistant", response)
                await self._save_chat_history(message.author.id, guild_id, content, response)

        if channel_id in self.roleplay_channels:
            roleplay_data = self.roleplay_channels[channel_id]
            if roleplay_data["awaiting_character"]:
                content = message.content.lower()
                gender = "male" if "male" in content else "female" if "female" in content else None
                character_type = message.content.split(gender, 1)[1].strip() if gender else message.content.strip()
                if gender and character_type:
                    roleplay_data["character_gender"] = gender
                    roleplay_data["character_type"] = character_type
                    roleplay_data["awaiting_character"] = False
                    self.roleplay_channels[channel_id] = roleplay_data
                    await message.channel.send(f"🎭 Roleplay mode activated! I'll act as a {gender} {character_type}. Let's begin!")
                else:
                    await message.channel.send("Please specify a gender (male/female) and a character type (e.g., teacher, astronaut).")
            elif message.author.id == roleplay_data["user_id"]:
                user_id = message.author.id
                if user_id not in self.conversation_history:
                    self.conversation_history[user_id] = []
                self.conversation_history[user_id].append({"role": "user", "parts": [{"text": message.content}]})
                if len(self.conversation_history[user_id]) > 5:
                    self.conversation_history[user_id] = self.conversation_history[user_id][-5:]
                async with message.channel.typing():
                    prompt = (f"You are a {roleplay_data['character_gender']} {roleplay_data['character_type']}. "
                              f"Respond in character. User's message: {message.content}")
                    response = await self._get_groq_response(prompt, [{"role": "user", "content": prompt}])
                    await message.reply(f"<@{message.author.id}>​ {response}", allowed_mentions=discord.AllowedMentions(users=True))
                    self.conversation_history[user_id].append({"role": "assistant", "parts": [{"text": response}]})

    async def _get_groq_response(self, message: str, context_messages: list) -> str:
        try:
            if not self.groq_api_key:
                return "Groq API key not configured. Please set the GROQ_API_KEY environment variable."
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.groq_api_key}", "Content-Type": "application/json"}
            api_messages = []
            for msg in context_messages:
                if isinstance(msg, dict):
                    if "content" in msg:
                        api_messages.append({"role": msg["role"], "content": msg["content"]})
                    elif "parts" in msg and msg["parts"]:
                        api_messages.append({"role": msg["role"], "content": msg["parts"][0].get("text", "")})
            data = {"model": "llama-3.3-70b-versatile", "messages": api_messages, "temperature": 0.8, "max_tokens": 1000, "top_p": 0.9}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status == 200:
                        json_response = await response.json()
                        return json_response['choices'][0]['message']['content'].strip()
                    else:
                        error_message = await response.text()
                        return f"API error: {response.status}"
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"

    async def _get_response(self, message: str, history: list, guild_id: int, user_id: int = None) -> str:
        try:
            user_personality = await self._get_user_personality(user_id, guild_id) if user_id else ""
            system_context = []
            if user_personality:
                system_context.append({"role": "system", "content": user_personality})
            system_context.append({"role": "system", "content": "You are Lucky Bot, an intelligent Discord bot assistant from lucky.gg. Be helpful and friendly. Support server: https://discord.gg/q2DdzFxheA"})
            full_context = system_context + history + [{"role": "user", "content": message}]
            return await self._get_groq_response(message, full_context)
        except Exception as e:
            return "Sorry, I encountered an error. Please try again!"

    @ai.command(name="analyse", description="Analyse an image or text using AI")
    async def ai_analyse(self, ctx: commands.Context, image_url: str = None):
        await ctx.defer()
        if ctx.message.reference and ctx.message.reference.message_id:
            try:
                replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if replied_message.attachments:
                    image_url = replied_message.attachments[0].url
                    embed = await self.analyze_image(ctx, image_url)
                    return await ctx.send(embed=embed)
                elif replied_message.content.strip():
                    return await self.analyze_text(ctx, replied_message.content)
            except discord.NotFound:
                pass
        if not image_url:
            async for message in ctx.channel.history(limit=20):
                if message.attachments:
                    image_url = message.attachments[0].url
                    break
            else:
                embed = discord.Embed(title="🖼️ Image / 📝 Text Analysis", description="No images or text found. Please provide an image URL or reply to a message.", color=0xFF4444)
                embed.set_footer(text="Lucky Bot • lucky.gg")
                return await ctx.send(embed=embed)
        embed = await self.analyze_image(ctx, image_url)
        await ctx.send(embed=embed)

    @ai.command(name="analyze", description="Analyze an image or text using AI")
    async def ai_analyze(self, ctx: commands.Context, image: discord.Attachment = None, *, text: str = None):
        await self.ai_analyse(ctx, image_url=image.url if image else None)

    async def analyze_image(self, ctx, image_url: str):
        try:
            if not self.gemini_api_key or not GEMINI_AVAILABLE:
                return discord.Embed(title="🖼️ Image Analysis", description="Gemini API key not configured.", color=0xFF4444)
            genai.configure(api_key=self.gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-pro')
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    image_data = await resp.read()
            image = Image.open(io.BytesIO(image_data))
            response = model.generate_content(["What is shown in this image? Provide a detailed description.", image])
            embed = discord.Embed(title="🖼️ Image Analysis", description=response.text, color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.set_image(url=image_url)
            embed.set_footer(text=f"Analyzed by {ctx.author} • Lucky Bot • lucky.gg")
            return embed
        except Exception as e:
            embed = discord.Embed(title="🖼️ Image Analysis", description=f"Failed to analyze image: {e}", color=0xFF4444)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return embed

    async def analyze_text(self, ctx, text_content: str):
        try:
            prompt = f"Analyze the following text content. Provide insights about its tone, sentiment, and main themes:\n\n{text_content}"
            analysis = await self._get_groq_response(prompt, [{"role": "user", "content": prompt}])
            embed = discord.Embed(title="📝 Text Analysis", description=analysis, color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Analyzed Text", value=text_content[:512] + "..." if len(text_content) > 512 else text_content, inline=False)
            embed.set_footer(text=f"Analyzed by {ctx.author} • Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(title="📝 Text Analysis", description=f"Failed to analyze text: {e}", color=0xFF4444)
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)

    @ai.command(name="code", description="Generate code in any programming language")
    @app_commands.describe(language="Programming language", description="Description of what the code should do")
    async def ai_code(self, ctx: commands.Context, language: str, *, description: str):
        await ctx.defer()
        prompt = f"Generate clean, working {language} code for: {description}. Only provide the code with minimal comments."
        try:
            code = await self._get_groq_response(prompt, [{"role": "user", "content": prompt}])
            formatted_code = f"```{language.lower()}\n{code}\n```"
            embed = discord.Embed(title="💻 Generated Code", description=f"**Language:** {language}\n**Task:** {description}\n\n{formatted_code[:3900]}", color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text=f"Generated for {ctx.author} • Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            pass

    @ai.command(name="explain", description="Explain a concept or topic in detail")
    @app_commands.describe(topic="Topic to explain", level="Explanation level (beginner/intermediate/advanced)")
    async def ai_explain(self, ctx: commands.Context, *, topic: str, level: str = "intermediate"):
        await ctx.defer()
        level_map = {"beginner": "in simple terms for beginners", "intermediate": "with moderate detail", "advanced": "in technical detail for advanced users"}
        level_instruction = level_map.get(level.lower(), "with moderate detail")
        prompt = f"Explain {topic} {level_instruction}. Make it clear and informative."
        try:
            explanation = await self._get_groq_response(prompt, [{"role": "user", "content": prompt}])
            embed = discord.Embed(title=f"📚 Explanation: {topic}", description=explanation[:4096], color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Level", value=level.capitalize(), inline=True)
            embed.set_footer(text=f"Explained for {ctx.author} • Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            pass

    @ai.command(name="conversation-clear", description="Clear your conversation history")
    async def ai_conversation_clear(self, ctx: commands.Context):
        user_id, guild_id = ctx.author.id, ctx.guild.id
        if user_id in self.conversation_history:
            del self.conversation_history[user_id]
        await self.bot.db.execute("DELETE FROM conversation_memory WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        await self.bot.db.commit()
        embed = discord.Embed(title="🧹 Conversation Cleared", description="Your conversation history has been cleared. The AI will start fresh.", color=0x57F287, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text="Lucky Bot • lucky.gg")
        await ctx.send(embed=embed, ephemeral=True)

    @ai.command(name="mood-analyzer", description="Analyze the mood/sentiment of text")
    @app_commands.describe(text="Text to analyze")
    async def ai_mood_analyzer(self, ctx: commands.Context, *, text: str):
        await ctx.defer()
        prompt = f"Analyze the mood and sentiment of this text. Provide the overall sentiment, emotional tone, and a brief explanation:\n\n{text}"
        try:
            analysis = await self._get_groq_response(prompt, [{"role": "user", "content": prompt}])
            embed = discord.Embed(title="😊 Mood Analysis", description=analysis, color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Analyzed Text", value=text[:512] + "..." if len(text) > 512 else text, inline=False)
            embed.set_footer(text=f"Analyzed for {ctx.author} • Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            pass

    @ai.command(name="personality", description="Set your personal AI personality (Slash command only)")
    async def ai_personality(self, ctx: commands.Context):
        if not hasattr(ctx, 'interaction') or not ctx.interaction:
            embed = discord.Embed(title="🎭 AI Personality", description="This command is only available as a slash command! Use `/ai personality` instead.", color=0xFF4444, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        current_personality = await self._get_user_personality(ctx.author.id, ctx.guild.id)
        modal = PersonalityModal(self, current_personality)
        await ctx.interaction.response.send_modal(modal)

    async def _get_user_personality(self, user_id: int, guild_id: int) -> str:
        try:
            async with self.bot.db.execute("SELECT personality FROM user_personalities WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else ""
        except Exception as e:
            return ""

    @ai.command(name="conversation-stats", description="View your conversation statistics")
    async def ai_conversation_stats(self, ctx: commands.Context):
        await ctx.defer()
        user_id, guild_id = ctx.author.id, ctx.guild.id
        stats = await self._get_conversation_stats(user_id, guild_id)
        if not stats:
            embed = discord.Embed(title="📊 Conversation Statistics", description="You don't have any conversation history yet! Start chatting to build history.", color=0x2F3136, timestamp=datetime.now(timezone.utc))
        else:
            from datetime import datetime as dt
            first_msg = dt.fromisoformat(stats["first_message"].replace('Z', '+00:00'))
            last_msg = dt.fromisoformat(stats["last_message"].replace('Z', '+00:00'))
            embed = discord.Embed(title="📊 Your Conversation Statistics", color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="💬 Total Messages", value=f"{stats['message_count']} messages", inline=True)
            embed.add_field(name="🕐 First Chat", value=f"<t:{int(first_msg.timestamp())}:R>", inline=True)
            embed.add_field(name="🕒 Last Chat", value=f"<t:{int(last_msg.timestamp())}:R>", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author} • Lucky Bot • lucky.gg")
        await ctx.send(embed=embed, ephemeral=True)

    @ai.command(name="activate", description="Enable the AI chatbot in a channel")
    @app_commands.describe(channel="Channel to activate AI in (optional)")
    async def ai_activate(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if not ctx.author.guild_permissions.manage_channels:
            embed = discord.Embed(title="🃏 Permission Denied", description="You need `Manage Channels` permission to activate AI chatbot.", color=0xFF4444, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        target_channel = channel or ctx.channel
        guild_id, channel_id = ctx.guild.id, target_channel.id
        await self.bot.db.execute("INSERT OR REPLACE INTO chatbot_settings (guild_id, enabled, chatbot_channel_id) VALUES (?, ?, ?)", (guild_id, 1, channel_id))
        await self.bot.db.commit()
        self.chatbot_enabled[guild_id] = True
        self.chatbot_channels[guild_id] = channel_id
        embed = discord.Embed(title="🍀 AI Chatbot Activated", description=f"AI chatbot has been enabled in {target_channel.mention}!\nI'll respond to all messages in that channel.", color=0x57F287, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Activated by {ctx.author} • Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @ai.command(name="deactivate", description="Disable the AI chatbot in the channel")
    async def ai_deactivate(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.manage_channels:
            embed = discord.Embed(title="🃏 Permission Denied", description="You need `Manage Channels` permission.", color=0xFF4444, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        guild_id = ctx.guild.id
        await self.bot.db.execute("INSERT OR REPLACE INTO chatbot_settings (guild_id, enabled, chatbot_channel_id) VALUES (?, ?, ?)", (guild_id, 0, None))
        await self.bot.db.commit()
        self.chatbot_enabled[guild_id] = False
        self.chatbot_channels.pop(guild_id, None)
        embed = discord.Embed(title="🔇 AI Chatbot Deactivated", description="AI chatbot has been disabled in this server.", color=0xFF4444, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Deactivated by {ctx.author} • Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @ai.command(name="summarize", description="Summarize a long text")
    @app_commands.describe(text="Text to summarize")
    async def ai_summarize(self, ctx: commands.Context, *, text: str = None):
        await ctx.defer()
        if ctx.message.reference and not text:
            try:
                replied_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if replied_message.content:
                    text = replied_message.content
            except Exception:
                pass
        if not text:
            embed = discord.Embed(title="📝 Text Summarizer", description="Please provide text to summarize or reply to a message.", color=0xFF4444, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        prompt = f"Please provide a clear and concise summary of the following text:\n\n{text}"
        try:
            summary = await self._get_groq_response(prompt, [{"role": "user", "content": prompt}])
            embed = discord.Embed(title="📝 Text Summary", description=summary, color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Original Text", value=text[:512] + "..." if len(text) > 512 else text, inline=False)
            embed.set_footer(text=f"Summarized for {ctx.author} • Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            pass

    @ai.command(name="ask", description="Ask the AI a question")
    @app_commands.describe(question="Question to ask")
    async def ai_ask(self, ctx: commands.Context, *, question: str):
        await ctx.defer()
        try:
            answer = await self._get_groq_response(question, [{"role": "user", "content": question}])
            embed = discord.Embed(title="🤖 AI Response", description=answer, color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.add_field(name="Your Question", value=question, inline=False)
            embed.set_footer(text=f"Asked by {ctx.author} • Lucky Bot • lucky.gg")
            await ctx.send(embed=embed)
        except Exception as e:
            pass

    @ai.command(name="fact", description="Get a random fact or fact on a specific topic")
    @app_commands.describe(topic="Topic to get a fact about (optional)")
    async def ai_fact(self, ctx: commands.Context, *, topic: str = None):
        await ctx.defer()
        await self.get_fact(ctx, topic)

    @ai.command(name="database-clear", description="Clear your AI conversation data and personality")
    async def ai_database_clear(self, ctx: commands.Context):
        await ctx.defer()
        user_id, guild_id = ctx.author.id, ctx.guild.id
        try:
            await self.bot.db.execute("DELETE FROM conversation_memory WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            await self.bot.db.execute("DELETE FROM chatbot_history WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            await self.bot.db.execute("DELETE FROM user_personalities WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            if user_id in self.conversation_history:
                del self.conversation_history[user_id]
            await self.bot.db.commit()
            embed = discord.Embed(title="🗑️ Your Data Cleared", description="Your AI data has been cleared.", color=0x57F287, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await ctx.send(embed=embed, ephemeral=True)
        except Exception as e:
            await ctx.send(f"🃏 Failed to clear data: {e}", ephemeral=True)

    async def _get_conversation_stats(self, user_id: int, guild_id: int) -> dict:
        try:
            async with self.bot.db.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM conversation_memory WHERE user_id = ? AND guild_id = ?", (user_id, guild_id)) as cursor:
                row = await cursor.fetchone()
                if row and row[0] > 0:
                    return {"message_count": row[0], "first_message": row[1], "last_message": row[2]}
                return None
        except Exception:
            return None

    async def _store_conversation_message(self, user_id: int, guild_id: int, role: str, content: str):
        try:
            await self.bot.db.execute("INSERT INTO conversation_memory (user_id, guild_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (user_id, guild_id, role, content, datetime.now(timezone.utc)))
            await self.bot.db.commit()
        except Exception:
            pass

    async def _get_conversation_history(self, user_id: int, guild_id: int, limit: int = 20) -> list:
        try:
            async with self.bot.db.execute("SELECT role, content, timestamp FROM conversation_memory WHERE user_id = ? AND guild_id = ? ORDER BY timestamp DESC LIMIT ?",
                (user_id, guild_id, limit * 2)) as cursor:
                rows = await cursor.fetchall()
                history = [{"role": role, "content": content} for role, content, _ in reversed(rows)]
                return history[-limit:]
        except Exception:
            return []

    async def _save_chat_history(self, user_id: int, guild_id: int, message: str, response: str):
        try:
            await self.bot.db.execute("INSERT INTO chatbot_history (user_id, guild_id, message, response, timestamp) VALUES (?, ?, ?, ?, ?)",
                (user_id, guild_id, message, response, datetime.now(timezone.utc).isoformat()))
            await self.bot.db.commit()
        except Exception:
            pass

    async def _cleanup_old_conversations(self):
        try:
            very_old_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            await self.bot.db.execute("DELETE FROM conversation_memory WHERE timestamp < ? AND NOT (content LIKE '%remember%' OR content LIKE '%my name is%' OR content LIKE '%i like%' OR content LIKE '%important%')", (very_old_cutoff,))
            await self.bot.db.execute("DELETE FROM conversation_memory WHERE rowid NOT IN (SELECT rowid FROM conversation_memory ORDER BY timestamp DESC LIMIT 100)")
            await self.bot.db.commit()
        except Exception:
            pass

    async def split_and_send(self, channel, content: str, reply_to=None, allowed_mentions=None):
        if len(content) <= 2000:
            if reply_to:
                await reply_to.reply(content, allowed_mentions=allowed_mentions)
            else:
                await channel.send(content, allowed_mentions=allowed_mentions)
        else:
            parts = []
            while len(content) > 2000:
                split_point = content.rfind(' ', 0, 2000)
                if split_point == -1:
                    split_point = 2000
                parts.append(content[:split_point])
                content = content[split_point:].lstrip()
            if content:
                parts.append(content)
            for i, part in enumerate(parts):
                if i == 0 and reply_to:
                    await reply_to.reply(part, allowed_mentions=allowed_mentions)
                else:
                    await channel.send(part, allowed_mentions=allowed_mentions)

    async def get_fact(self, ctx, topic: Optional[str]):
        fact = None
        max_attempts = 3
        for attempt in range(max_attempts):
            prompt = (f"Provide a concise, interesting fact{' on the topic of ' + topic if topic else ''}. Keep it under 200 characters. "
                      "Format the response as:\nFact: [Your fact here]")
            try:
                text = await self._get_groq_response(prompt, [{"role": "user", "content": prompt}])
                if "Fact:" in text:
                    fact = text.split("Fact:")[1].strip().strip('."\' ')
                    if len(fact) > 5:
                        break
            except Exception:
                pass

        if not fact:
            fallback_facts = ["A day on Venus is longer than a year on Venus.", "Honey never spoils.", "Octopuses have three hearts and blue blood.", "Bananas are berries, but strawberries aren't.", "Sharks have been around longer than trees."]
            fact = random.choice(fallback_facts)

        embed = discord.Embed(title="🌟 Fun Fact!", description=fact, color=0x2F3136, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Requested by {ctx.author} • Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    async def generate_trivia_question(self, category: str, used_questions: list):
        effective_category = category if category != "mixed" else categories[random.randint(0, len(categories) - 1)]
        category_key = effective_category.replace(" ", "_").lower()
        cached = [q for q in self.question_cache.get(category_key, []) if q["question"] not in used_questions]
        if cached:
            return random.choice(cached)
        for attempt in range(5):
            prompt = (f"Generate a unique trivia question in category '{effective_category}'.\n"
                      "Format:\nQuestion: [question]\nAnswer: [correct answer]\nIncorrect 1: [wrong]\nIncorrect 2: [wrong]")
            try:
                text = await self._get_groq_response(prompt, [{"role": "user", "content": prompt}])
                if "Question:" in text and "Answer:" in text:
                    question = text.split("Question:")[1].split("\n")[0].strip()
                    answer = text.split("Answer:")[1].split("\n")[0].strip()
                    incorrect_answers = []
                    if "Incorrect 1:" in text:
                        incorrect_answers.append(text.split("Incorrect 1:")[1].split("\n")[0].strip())
                    if "Incorrect 2:" in text:
                        incorrect_answers.append(text.split("Incorrect 2:")[1].strip().split("\n")[0])
                    while len(incorrect_answers) < 2:
                        incorrect_answers.append(f"Option {len(incorrect_answers) + 1}")
                    if question not in used_questions and len(question) > 5:
                        question_data = {"question": question, "answer": answer, "incorrect_answers": incorrect_answers[:2]}
                        self.question_cache.setdefault(category_key, []).append(question_data)
                        return question_data
            except Exception:
                pass
        available = [q for q in fallback_questions.get(category_key, fallback_questions["general"]) if q["question"] not in used_questions]
        if available:
            q = random.choice(available)
            q["incorrect_answers"] = ["Wrong Answer 1", "Wrong Answer 2"]
            return q
        return None

    async def evaluate_answer(self, correct_answer: str, user_answer: str):
        prompt = (f"Determine if the user's answer '{user_answer}' is correct compared to '{correct_answer}'. "
                  "Consider synonyms and minor variations. Respond with 'true' or 'false'.")
        try:
            text = await self._get_groq_response(prompt, [{"role": "user", "content": prompt}])
            return "true" in text.lower()
        except Exception:
            return correct_answer.lower().strip() == user_answer.lower().strip()

    async def start_trivia_game(self, ctx, category: Optional[str]):
        channel_id = ctx.channel.id
        if channel_id in self.active_games:
            embed = discord.Embed(title="🧠 Trivia Game", description="A trivia game is already active in this channel!", color=0xFF4444, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        effective_category = category.lower() if category else "mixed"
        question_data = await self.generate_trivia_question(effective_category, [])
        if not question_data:
            embed = discord.Embed(title="🧠 Trivia Game", description="Failed to generate a trivia question. Try again later.", color=0xFF4444, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        self.active_games[channel_id] = {"category": effective_category, "current_question": question_data["question"], "current_answer": question_data["answer"], "incorrect_answers": question_data["incorrect_answers"], "scores": {}, "round": 1, "max_rounds": 5, "used_questions": [question_data["question"]], "answered": False}
        view = TriviaAnswerView(self, channel_id, question_data["answer"], question_data["incorrect_answers"])
        embed = discord.Embed(title="🧠 Trivia Game", description=f"**Round 1/{self.active_games[channel_id]['max_rounds']}**\nCategory: {category or 'Mixed'}\n{question_data['question']}", color=0x2F3136, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text="Click a button to answer! • Lucky Bot • lucky.gg")
        await ctx.send(embed=embed, view=view)

    async def handle_trivia_answer(self, interaction: discord.Interaction, channel_id: int, selected_answer: str):
        await interaction.response.defer()
        game = self.active_games.get(channel_id)
        if not game:
            return await interaction.followup.send("No trivia game is active!", ephemeral=True)
        if game["answered"]:
            return await interaction.followup.send("This question has already been answered!", ephemeral=True)
        game["answered"] = True
        user_id = interaction.user.id
        username = interaction.user.display_name
        is_correct = await self.evaluate_answer(game["current_answer"], selected_answer)
        user_score = game["scores"].get(user_id, 0) + (1 if is_correct else -1)
        game["scores"][user_id] = user_score
        await self.trivia_scores.find_one_and_update({"userId": user_id}, {"username": username, "$inc": {"score": 1 if is_correct else -1, "gamesPlayed": 1}, "$push": {"history": {"score": 1 if is_correct else -1, "category": game["category"]}}}, upsert=True)
        response_message = (f"🎉 Correct! The answer was **{game['current_answer']}**. +1 point!" if is_correct else f"🃏 Incorrect. The answer was **{game['current_answer']}**. Your guess: **{selected_answer}**. -1 point.")
        question_data = await self.generate_trivia_question(game["category"], game["used_questions"][-5:])
        if not question_data:
            del self.active_games[channel_id]
            embed = discord.Embed(title="🧠 Trivia Game", description="Failed to generate the next question. Game ended.", color=0xFF4444, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await interaction.followup.send(embed=embed)
        game.update({"current_question": question_data["question"], "current_answer": question_data["answer"], "incorrect_answers": question_data["incorrect_answers"], "answered": False})
        game["used_questions"].append(question_data["question"])
        game["round"] += 1
        if game["round"] > game["max_rounds"]:
            response_message += "\n\n**Game Over!**\nScores:\n"
            for uid, score in game["scores"].items():
                try:
                    user = await interaction.guild.fetch_member(uid)
                    response_message += f"- {user.display_name if user else 'Unknown'}: {score}\n"
                except Exception:
                    pass
            del self.active_games[channel_id]
            embed = discord.Embed(title="🧠 Trivia Game", description=response_message, color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            await interaction.followup.send(embed=embed)
        else:
            response_message += f"\n\n**Round {game['round']}/{game['max_rounds']}**\n{game['current_question']}"
            view = TriviaAnswerView(self, channel_id, game["current_answer"], game["incorrect_answers"])
            embed = discord.Embed(title="🧠 Trivia Game", description=response_message, color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Click a button to answer! • Lucky Bot • lucky.gg")
            await interaction.followup.send(embed=embed, view=view)

    async def show_stats(self, ctx):
        user_id = ctx.author.id
        stats = await self.trivia_scores.find_one({"userId": user_id})
        if not stats:
            embed = discord.Embed(title="🧠 Trivia Statistics", description="You haven't played any trivia games yet!", color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        total_games = stats["gamesPlayed"]
        total_correct = sum(1 for h in stats["history"] if h["score"] > 0)
        win_rate = (total_correct / total_games * 100) if total_games > 0 else 0
        embed = discord.Embed(title="🧠 Your Trivia Statistics",
            description=f"**Total Score:** {stats['score']}\n**Games Played:** {total_games}\n**Correct Answers:** {total_correct}\n**Win Rate:** {win_rate:.2f}%",
            color=0x2F3136, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Requested by {ctx.author} • Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    async def show_leaderboard(self, ctx):
        top_scores = await self.trivia_scores.find()
        if not top_scores:
            embed = discord.Embed(title="🏆 Trivia Leaderboard", description="No scores yet! Play a trivia game to get started.", color=0x2F3136, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        leaderboard = ""
        for index, entry in enumerate(top_scores, 1):
            emoji = "🥇" if index == 1 else "🥈" if index == 2 else "🥉" if index == 3 else f"{index}."
            leaderboard += f"{emoji} {entry['username']}: {entry['score']}\n"
        embed = discord.Embed(title="🏆 Trivia Leaderboard", description=leaderboard, color=0x2F3136, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Requested by {ctx.author} • Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @ai.command(name="roleplay-enable", description="Enable roleplay mode in the current channel")
    async def ai_roleplay_enable(self, ctx: commands.Context):
        channel_id = ctx.channel.id
        if channel_id in self.roleplay_channels:
            embed = discord.Embed(title="🎭 Roleplay Mode", description="Roleplay mode is already enabled! Use `/ai roleplay-disable` to turn it off.", color=0xFF4444, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        self.roleplay_channels[channel_id] = {"user_id": ctx.author.id, "character_gender": None, "character_type": None, "awaiting_character": True}
        embed = discord.Embed(title="🎭 Roleplay Mode", description="Roleplay mode activated! Tell me what kind of character you want me to be.\nExample: `female teacher` or `male astronaut`.", color=0x57F287, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Activated by {ctx.author} • Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)

    @ai.command(name="roleplay-disable", description="Disable roleplay mode in the current channel")
    async def ai_roleplay_disable(self, ctx: commands.Context):
        channel_id = ctx.channel.id
        if channel_id not in self.roleplay_channels:
            embed = discord.Embed(title="🎭 Roleplay Mode", description="Roleplay mode is not enabled! Use `/ai roleplay-enable` to turn it on.", color=0xFF4444, timestamp=datetime.now(timezone.utc))
            embed.set_footer(text="Lucky Bot • lucky.gg")
            return await ctx.send(embed=embed)
        del self.roleplay_channels[channel_id]
        embed = discord.Embed(title="🎭 Roleplay Mode", description="Roleplay mode disabled.", color=0xFF4444, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Disabled by {ctx.author} • Lucky Bot • lucky.gg")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AI(bot))

# Lucky Bot — Rewritten
