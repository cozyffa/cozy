import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
import uuid
import time

# ==================== CONFIGURATION ====================
TEST_GUILD_ID = 1452241505719681049      # Your Server ID
RESULTS_CHANNEL_ID = 1528716272865382520  # /result always posts here
DATA_FILE = "queue_data.json"             # Where queues / open panels are saved so a restart doesn't wipe them
QUEUE_MAX_SIZE = 10                        # Shown as "x/10" on the queue card; change here if you want a different cap
COOLDOWN_SECONDS = 5 * 24 * 60 * 60         # 5 days — how long a player must wait before rejoining the SAME kit after their ticket closes
TICKET_CATEGORY_ID = 1549195391160033381    # Every ticket channel gets created here instead of matching the queue channel's category

intents = discord.Intents.default()
intents.guilds = True   # Needed for basic server/channel access
intents.members = True  # Needed so /updatetierlist and the auto-refresh can scan every member's roles

bot = commands.Bot(command_prefix="!", intents=intents)

TIERS = ["S+", "S", "S-", "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-"]

# Single source of truth for every kit: label shown to users, emoji, category, and the
# role required to test it. Everything else (dropdown, choices, lookups) is built from this
# instead of being retyped in five different places, which is where the old bugs crept in.
KITS = {
    "Sword":         {"label": "Sword • FT6",           "emoji": "⚔️", "role": 1529271109738823803, "ping_role": 1548364714864677144, "queue_channel": 1548918406013526137},
    "Axe":           {"label": "Axe • FT6",             "emoji": "🪓", "role": 1548471426552565760, "ping_role": 1548472205296279763, "queue_channel": 1548896402543747082},
    "NPot":          {"label": "NethPot • FT2",         "emoji": "🧪", "role": 1548352220221939732, "ping_role": 1548364883639148674, "queue_channel": 1548898461502668820},
    "DPot":          {"label": "DPot • FT2",            "emoji": "🏺", "role": 1548471627539546243, "ping_role": 1548472400117629078, "queue_channel": 1548898394523574332},
    "DiaSMP":        {"label": "DiaSMP • FT3",          "emoji": "💎", "role": 1529270774387707915, "ping_role": 1548364663937306664, "queue_channel": 1548898209714278401},
    "NetherSMP":     {"label": "NetherSMP • FT2",       "emoji": "🔥", "role": 1548471516964978820, "ping_role": 1548472066959867964, "queue_channel": 1548898304023339048},
    "Mace":          {"label": "Mace • FT3",            "emoji": "🔨", "role": 1529270991937867856, "ping_role": 1548364804735893636, "queue_channel": 1548895861063549008},
    "Spear Mace":    {"label": "Spear Mace • FT3",      "emoji": "🔱", "role": 1548471143730647172, "ping_role": 1548472316038610974, "queue_channel": 1548896255080407110},
    "UHC":           {"label": "UHC • FT3",             "emoji": "🏹", "role": 1548352120598827041, "ping_role": 1548364838651166842, "queue_channel": 1548898689840578590},
    "Cart":          {"label": "Cart",                  "emoji": "🧨", "role": 1548473865489883289, "ping_role": 1548364941717672017, "queue_channel": 1548896331903410176},
}

KIT_CHOICES = [app_commands.Choice(name=info["label"], value=key) for key, info in KITS.items()]
TIER_CHOICES = [app_commands.Choice(name=t, value=t) for t in TIERS]

# Where each kit's auto-updating leaderboard lives, and the short title used in its header
TIERLIST_CONFIG = {
    "NetherSMP":   {"channel": 1528711256498901023, "title": "NSMP"},
    "DiaSMP":      {"channel": 1528712196677304380, "title": "DSMP"},
    "Mace":        {"channel": 1528712096362270740, "title": "MACE"},
    "Spear Mace":  {"channel": 1549203188467503215, "title": "SPEARMACE"},
    "Sword":       {"channel": 1528711993782173857, "title": "SWORD"},
    "Axe":         {"channel": 1549203094816948324, "title": "AXE"},
    "NPot":        {"channel": 1528711797673295903, "title": "NPOT"},
    "DPot":        {"channel": 1549202622291124234, "title": "DPOT"},
    "Cart":        {"channel": 1528711725594185878, "title": "CART"},
    "UHC":         {"channel": 1549202511636865095, "title": "UHC"},
}

TIER_EMOJIS = {
    "S+": "🏆", "S": "🥇", "S-": "🥈", "A+": "🥉", "A": "⭐", "A-": "🎖️",
    "B+": "🔥", "B": "🟢", "B-": "🔰", "C+": "🟡", "C": "🔵", "C-": "⚪",
}


def to_bold_serif(text: str) -> str:
    """Converts plain text to 𝐁𝐨𝐥𝐝 𝐒𝐞𝐫𝐢𝐟 Unicode (used for leaderboard titles)."""
    out = []
    for c in text:
        if "A" <= c <= "Z":
            out.append(chr(ord(c) + 0x1D400 - ord("A")))
        elif "a" <= c <= "z":
            out.append(chr(ord(c) + 0x1D41A - ord("a")))
        elif "0" <= c <= "9":
            out.append(chr(ord(c) + 0x1D7CE - ord("0")))
        else:
            out.append(c)
    return "".join(out)


def to_bold_sans(text: str) -> str:
    """Converts plain text to 𝗕𝗼𝗹𝗱 𝗦𝗮𝗻𝘀 Unicode (used for tier labels and footer text)."""
    out = []
    for c in text:
        if "A" <= c <= "Z":
            out.append(chr(ord(c) + 0x1D5D4 - ord("A")))
        elif "a" <= c <= "z":
            out.append(chr(ord(c) + 0x1D5EE - ord("a")))
        elif "0" <= c <= "9":
            out.append(chr(ord(c) + 0x1D7EC - ord("0")))
        else:
            out.append(c)
    return "".join(out)


# Tier role IDs per kit. A value of None means that tier's role hasn't been created/given yet —
# /result will still work, it just skips the automatic role swap for that specific tier/kit and
# tells the tester so in the confirmation message, instead of failing outright.
KIT_TIER_ROLES = {
    "UHC": {
        "S+": 1548476879378579536, "S": 1548477090062671964, "S-": 1548477141258080358,
        "A+": 1548477164154921011, "A": 1548477213047918650, "A-": 1548477241975902228,
        "B+": 1548477270920929290, "B": 1548477312637608096, "B-": 1548477340185665586,
        "C+": 1548477363996860497, "C": 1548477404840988805, "C-": 1548477429943636059,
    },
    "DiaSMP": {
        "S+": 1548479472620146750, "S": 1548480437192499241, "S-": 1548480497284546643,
        "A+": 1548480535683137536, "A": 1548480564145823894, "A-": 1548480593719857192,
        "B+": 1548480612644425748, "B": 1548480652914196501, "B-": 1548480660359086160,
        "C+": 1548480715727962202, "C": 1548480755804541028, "C-": 1548480749441650828,
    },
    "NetherSMP": {
        "S+": 1548481090937684090, "S": 1548481183065837708, "S-": 1548481224719470744,
        "A+": 1548481258282033283, "A": 1548481294751637525, "A-": 1548481298543284255,
        "B+": 1548481388926210158, "B": 1548481401140158645, "B-": 1548481396773879838,
        "C+": 1548481494333395107, "C": 1548481529657958500, "C-": 1548481566928412682,
    },
    "Sword": {
        "S+": 1548482595484860516, "S": 1548482732957368501, "S-": 1548482740847120495,
        "A+": 1548482841590112286, "A": 1548482873731055697, "A-": 1548482985534427156,
        "B+": 1548483030115684502, "B": 1548483040433541171, "B-": 1548483045756117123,
        "C+": 1548483154841440369, "C": 1548483190455279757, "C-": 1548483212165128334,
    },
    "Axe": {
        "S+": 1548484315224997918, "S": 1548484387564290089, "S-": 1548484410901528596,
        "A+": 1548484455449231370, "A": 1548484451510657054, "A-": 1548484438877413486,
        "B+": 1548484442656604190, "B": 1548484448067133561, "B-": 1548484612953604186,
        "C+": 1548484609069682810, "C": 1548484681622749265, "C-": 1548484684978200636,
    },
    "DPot": {
        "S+": 1548490370109673492, "S": 1548490517741051987, "S-": 1548490521742278706,
        "A+": 1548490527702515732, "A": 1548490589857783828, "A-": 1548490601412952115,
        "B+": 1548490596350566410, "B": 1548490611550589018, "B-": 1548490617259032657,
        "C+": 1548490642965925968, "C": 1548490656433971301, "C-": 1548490649492267088,
    },
    "NPot": {
        "S+": 1548490930842112031, "S": 1548491141953884230, "S-": 1548491123117396119,
        "A+": 1548491106067685418, "A": 1548491079618400316, "A-": 1548491067832406027,
        "B+": 1548491072429359145, "B": 1548491093136510986, "B-": 1548491099918565429,
        "C+": 1548491114225606717, "C": 1548491130981720084, "C-": 1548491177974702160,
    },
    "Cart": {
        "S+": 1548723300631576736, "S": 1548723415387471962, "S-": 1548723421989441769,
        "A+": 1548723427085647882, "A": 1548723438078795776, "A-": 1548723451752349737,
        "B+": 1548723444047155341, "B": 1548723464263704738, "B-": 1548723696188002434,
        "C+": 1548723762285907998, "C": 1548723767927246848, "C-": 1548723773698613489,
    },
    "Spear Mace": {
        "S+": 1548724735238471881, "S": 1548726534867648573, "S-": 1548724803437989918,
        "A+": 1548724849869066370, "A": 1548724856877752360, "A-": 1548724862502305893,
        "B+": 1548725118430347285, "B": 1548725126907043951, "B-": 1548725134406459402,
        "C+": 1548725262986907750, "C": 1548725270129807480, "C-": 1548725276370804787,
    },
    "Mace": {
        "S+": 1548724228210298992, "S": 1548724363816214528, "S-": 1548724371663884370,
        "A+": 1548724431210151956, "A": 1548724438327885825, "A-": 1548724443814174760,
        "B+": 1548724454375292990, "B": 1548724466849292410, "B-": 1548724473019240489,
        "C+": 1548724613150679110, "C": 1548724619282747594, "C-": 1548724629756059678,
    },
}


# ==================== STATE + PERSISTENCE ====================
class QueueManager:
    """
    Holds every kit queue plus the open-panel messages, and saves itself to disk
    after every change. Players are stored as user IDs (not live discord.Member
    objects) so this can be dumped straight to JSON and survives a bot restart
    instead of silently losing every queue the moment the process stops.

    user_index gives an O(1) "is this person already queued somewhere?" lookup
    instead of the old approach, which looped every player in every queue on
    every single join.
    """
    def __init__(self):
        self.queues = {kit: [] for kit in KITS}          # kit -> list of {"user_id", "name_ans", ...extra}
        self.user_index = {}                              # user_id -> kit currently queued in
        self.open_panels = {}                              # kit -> {"channel_id", "message_id", "queue_id", "locked", "tester_id"}
        self.ticket_players = {}                           # str(channel_id) -> {"user_id", "name_ans", "kit"}
        self.cooldowns = {}                                 # str(user_id) -> {kit: expiry_unix_timestamp}
        self.last_session = {}                              # kit -> unix timestamp of when its queue was last closed
        self.last_message = {}                              # kit -> {"channel_id", "message_id"} of the most recent panel/closed card, even after closing
        self.tierlist_message = {}                          # kit -> {"channel_id", "message_id"} of the posted leaderboard message
        self.player_igns = {}                               # str(user_id) -> most recently known Minecraft IGN
        self.load()

    def load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    data = json.load(f)
                self.queues = data.get("queues", {kit: [] for kit in KITS})
                self.open_panels = data.get("open_panels", {})
                self.ticket_players = data.get("ticket_players", {})
                self.cooldowns = data.get("cooldowns", {})
                self.last_session = data.get("last_session", {})
                self.last_message = data.get("last_message", {})
                self.tierlist_message = data.get("tierlist_message", {})
                self.player_igns = data.get("player_igns", {})
                for kit, players in self.queues.items():
                    for p in players:
                        self.user_index[p["user_id"]] = kit
            except (json.JSONDecodeError, OSError):
                pass  # start fresh if the file is missing/corrupt

    def save(self):
        with open(DATA_FILE, "w") as f:
            json.dump({
                "queues": self.queues,
                "open_panels": self.open_panels,
                "ticket_players": self.ticket_players,
                "cooldowns": self.cooldowns,
                "last_session": self.last_session,
                "last_message": self.last_message,
                "tierlist_message": self.tierlist_message,
                "player_igns": self.player_igns,
            }, f)

    def set_cooldown(self, user_id: int, kit: str):
        key = str(user_id)
        self.cooldowns.setdefault(key, {})[kit] = time.time() + COOLDOWN_SECONDS
        self.save()

    def get_cooldown_remaining(self, user_id: int, kit: str):
        """Returns remaining seconds if still on cooldown for this kit, else None."""
        expiry = self.cooldowns.get(str(user_id), {}).get(kit)
        if expiry is None:
            return None
        remaining = expiry - time.time()
        return remaining if remaining > 0 else None

    def get_all_cooldowns(self, user_id: int):
        """Returns {kit: remaining_seconds} for every kit still on cooldown for this user."""
        entries = self.cooldowns.get(str(user_id), {})
        now = time.time()
        return {kit: (expiry - now) for kit, expiry in entries.items() if expiry > now}

    def record_ticket(self, channel_id: int, user_id: int, name_ans: str, kit: str):
        self.ticket_players[str(channel_id)] = {"user_id": user_id, "name_ans": name_ans, "kit": kit}
        self.save()

    def get_ticket_player(self, channel_id: int):
        return self.ticket_players.get(str(channel_id))

    def already_queued(self, user_id: int):
        return self.user_index.get(user_id)  # returns kit name, or None

    def join(self, kit: str, user_id: int, name_ans: str, **extra) -> int:
        self.queues[kit].append({"user_id": user_id, "name_ans": name_ans, **extra})
        self.user_index[user_id] = kit
        self.save()
        return len(self.queues[kit])

    def leave(self, user_id: int):
        kit = self.user_index.pop(user_id, None)
        if kit is None:
            return None
        self.queues[kit] = [p for p in self.queues[kit] if p["user_id"] != user_id]
        self.save()
        return kit

    def pop_next(self, kit: str):
        if not self.queues.get(kit):
            return None
        player = self.queues[kit].pop(0)
        self.user_index.pop(player["user_id"], None)
        self.save()
        return player

    def set_panel(self, kit: str, channel_id: int, message_id: int, tester_id: int = None):
        self.open_panels[kit] = {
            "channel_id": channel_id,
            "message_id": message_id,
            "queue_id": uuid.uuid4().hex[:12],
            "locked": False,
            "tester_id": tester_id,
        }
        self.save()

    def clear_panel(self, kit: str):
        self.open_panels.pop(kit, None)
        self.save()

    def record_close(self, kit: str):
        self.last_session[kit] = time.time()
        self.save()

    def record_message(self, kit: str, channel_id: int, message_id: int):
        self.last_message[kit] = {"channel_id": channel_id, "message_id": message_id}
        self.save()

    def record_tierlist_message(self, kit: str, channel_id: int, message_id: int):
        self.tierlist_message[kit] = {"channel_id": channel_id, "message_id": message_id}
        self.save()

    def set_ign(self, user_id: int, ign: str):
        self.player_igns[str(user_id)] = ign
        self.save()

    def get_ign(self, user_id: int) -> str:
        return self.player_igns.get(str(user_id))

    def set_locked(self, kit: str, locked: bool):
        if kit in self.open_panels:
            self.open_panels[kit]["locked"] = locked
            self.save()

    def set_tester(self, kit: str, tester_id: int):
        if kit in self.open_panels:
            self.open_panels[kit]["tester_id"] = tester_id
            self.save()


queues = QueueManager()


def has_tester_role(member: discord.Member, kit: str) -> bool:
    if member.guild_permissions.administrator:
        return True
    role_id = KITS[kit]["role"]
    return any(r.id == role_id for r in member.roles)


TIER_TESTER_ROLE_ID = 1501209489867673700  # Can run queue-management commands without needing Administrator


def is_tier_tester():
    """App command check: passes for admins OR anyone holding the Tier Tester role."""
    def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if member.guild_permissions.administrator:
            return True
        return any(r.id == TIER_TESTER_ROLE_ID for r in member.roles)
    return app_commands.check(predicate)


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes and not days:  # keep it short once we're into multi-day territory
        parts.append(f"{minutes}m")
    return " ".join(parts) if parts else "less than a minute"


# ==================== APPLICATION MODAL ====================
class TierApplicationModal(discord.ui.Modal, title="Cozy SMP Tier Test Application"):
    player_name = discord.ui.TextInput(
        label="Name",
        placeholder="Enter your name or Minecraft IGN...",
        required=True,
        max_length=20,
    )
    gamemode_input = discord.ui.TextInput(
        label="What gamemode",
        placeholder="e.g., Sword • FT6",
        required=True,
        max_length=30,
    )

    def __init__(self, kit: str):
        super().__init__()
        self.kit = kit
        self.gamemode_input.default = KITS[kit]["label"]

    async def on_submit(self, interaction: discord.Interaction):
        existing_kit = queues.already_queued(interaction.user.id)
        if existing_kit:
            await interaction.response.send_message(
                f"❌ You are already waiting in the **{KITS[existing_kit]['label']}** queue! Leave it first.",
                ephemeral=True,
            )
            return

        position = queues.join(self.kit, interaction.user.id, self.player_name.value, self.gamemode_input.value)
        queues.set_ign(interaction.user.id, self.player_name.value)

        await interaction.response.send_message(
            f"✅ **Application Submitted!**\n"
            f"Joined the **{KITS[self.kit]['label']}** queue at position **#{position}**.\n"
            f"👤 Name: `{self.player_name.value}` | ⚔️ Mode: `{self.gamemode_input.value}`",
            ephemeral=True,
        )


# ==================== MAIN PANEL (all kits, dropdown) ====================
class KitDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=info["label"], value=key, emoji=info["emoji"])
            for key, info in KITS.items()
        ]
        super().__init__(placeholder="Choose a kit to join...", min_values=1, max_values=1, options=options, custom_id="kit_dropdown")

    async def callback(self, interaction: discord.Interaction):
        selected_kit = self.values[0]  # .values is always a list, even with max_values=1 - grab the single item
        await interaction.response.send_modal(TierApplicationModal(selected_kit))


class WaitlistView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(KitDropdown())
        # Link buttons never fire a Python callback, so it's added directly instead of via the
        # @discord.ui.button decorator, which implies interaction handling that would never run.
        self.add_item(discord.ui.Button(label="Queue Status", style=discord.ButtonStyle.link, url="https://discord.com", emoji="❓"))

    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.danger, custom_id="leave_queue_btn", emoji="❌")
    async def leave_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        kit = queues.leave(interaction.user.id)
        if kit:
            await interaction.response.send_message(f"👋 You have successfully left the **{KITS[kit]['label']}** queue.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You are not currently waiting in any kit queue lines.", ephemeral=True)

    @discord.ui.button(label="View My Cooldown", style=discord.ButtonStyle.secondary, custom_id="cooldown_btn", emoji="⏳")
    async def view_cooldown(self, interaction: discord.Interaction, button: discord.ui.Button):
        active = queues.get_all_cooldowns(interaction.user.id)
        if not active:
            await interaction.response.send_message("⏳ You do not have an active testing cooldown right now.", ephemeral=True)
            return
        lines = [f"**{KITS[kit]['label']}** — {format_duration(remaining)} remaining" for kit, remaining in active.items()]
        await interaction.response.send_message("⏳ **Active Cooldowns:**\n" + "\n".join(lines), ephemeral=True)


def create_cozy_embed():
    embed = discord.Embed(
        title="⚔️ Cozy SMP Tier Test Waitlist",
        description=(
            "A clean control panel for joining, leaving, and checking cooldowns.\n"
            "Pick a kit below to open the join form, then use the quick actions if you need to leave or check cooldowns.\n\n"
            "⚔️ **Sword**\n↳ Sword • FT6\n↳ Axe • FT6\n\n"
            "🧪 **Pots**\n↳ NPot • FT2\n↳ DPot • FT2\n\n"
            "💎 **SMP**\n↳ DiaSMP • FT3\n↳ NetherSMP • FT2\n\n"
            "🔨 **Mace**\n↳ Mace • FT3\n↳ Spear Mace • FT3\n\n"
            "🏹 **UHC**\n↳ UHC • FT3\n\n"
            "🧨 **Cart**"
        ),
        color=discord.Color.from_rgb(255, 140, 0),
    )
    return embed


# ==================== QUEUE CARD SYSTEM (for /openqueue) ====================
def make_progress_bar(current: int, maximum: int, length: int = 10) -> str:
    filled = round((current / maximum) * length) if maximum else 0
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)


def build_closed_embed(kit: str) -> discord.Embed:
    description = (
        "There's no available tester at the time.\n"
        "You will be pinged when a tester is available.\n"
        "Comeback later!"
    )
    last_closed = queues.last_session.get(kit)
    if last_closed:
        description += f"\n\n*Last testing session: <t:{int(last_closed)}:R>*"

    return discord.Embed(
        title=f"{KITS[kit]['emoji']} {KITS[kit]['label']} Queue",
        description=description,
        color=discord.Color.from_rgb(255, 140, 0),
    )


def build_queue_embed(kit: str) -> discord.Embed:
    panel = queues.open_panels[kit]
    players = queues.queues[kit]
    count = len(players)
    max_size = QUEUE_MAX_SIZE
    status = "🔒 Locked" if panel["locked"] else "🟢 Open"
    tester_value = f"<@{panel['tester_id']}>" if panel.get("tester_id") else "Unassigned"
    next_value = players[0]["name_ans"] if players else "None"

    embed = discord.Embed(
        title=f"{'🔒' if panel['locked'] else '🟢'} {KITS[kit]['label']} Queue",
        color=discord.Color.from_rgb(255, 140, 0),
    )

    if players:
        lines = [f"`{i}.` **{p['name_ans']}** — <@{p['user_id']}>" for i, p in enumerate(players[:max_size], start=1)]
        embed.add_field(name=f"Players in Queue • {count} Players", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="Players in Queue • 0 Players", value="_No one is waiting yet._", inline=False)

    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Tester", value=tester_value, inline=True)
    embed.add_field(name="Next", value=f"➡️ {next_value}", inline=True)
    embed.set_footer(text=f"Queue ID: {panel['queue_id']}")
    return embed


class JoinQueueModal(discord.ui.Modal, title="Join the Queue"):
    player_name = discord.ui.TextInput(
        label="Name / IGN",
        placeholder="Enter your name or Minecraft IGN...",
        required=True,
        max_length=20,
    )

    def __init__(self, kit: str):
        super().__init__()
        self.kit = kit

    async def on_submit(self, interaction: discord.Interaction):
        panel = queues.open_panels.get(self.kit)
        if not panel:
            await interaction.response.send_message("❌ This queue is no longer open.", ephemeral=True)
            return
        if panel["locked"]:
            await interaction.response.send_message("🔒 This queue is currently locked and not accepting new joins.", ephemeral=True)
            return

        existing_kit = queues.already_queued(interaction.user.id)
        if existing_kit:
            await interaction.response.send_message(
                f"❌ You are already waiting in the **{KITS[existing_kit]['label']}** queue! Leave it first.",
                ephemeral=True,
            )
            return

        remaining = queues.get_cooldown_remaining(interaction.user.id, self.kit)
        if remaining:
            await interaction.response.send_message(
                f"⏳ You're on cooldown for **{KITS[self.kit]['label']}** for another {format_duration(remaining)}.",
                ephemeral=True,
            )
            return

        position = queues.join(self.kit, interaction.user.id, self.player_name.value)
        queues.set_ign(interaction.user.id, self.player_name.value)
        await interaction.response.send_message(
            f"✅ Joined the **{KITS[self.kit]['label']}** queue at position **#{position}**.", ephemeral=True
        )
        await refresh_panel_message(self.kit)


async def refresh_panel_message(kit: str):
    """Re-fetches and edits the queue card message directly (used after modal submissions,
    which aren't tied to the panel message the way a button press is)."""
    panel = queues.open_panels.get(kit)
    if not panel:
        return
    try:
        channel = bot.get_channel(panel["channel_id"]) or await bot.fetch_channel(panel["channel_id"])
        message = await channel.fetch_message(panel["message_id"])
        await message.edit(embed=build_queue_embed(kit), view=QueueControlView(kit))
    except (discord.NotFound, discord.Forbidden):
        pass


class TicketControlView(discord.ui.View):
    """Skip/Close buttons on a ticket's welcome message, so a tester doesn't have to
    remember or type /close_test manually."""
    def __init__(self, kit: str, channel_id: int):
        super().__init__(timeout=None)
        self.kit = kit

        skip_btn = discord.ui.Button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️", custom_id=f"ticket_skip::{channel_id}")
        skip_btn.callback = self.skip_callback
        self.add_item(skip_btn)

        close_btn = discord.ui.Button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id=f"ticket_close::{channel_id}")
        close_btn.callback = self.close_callback
        self.add_item(close_btn)

    async def _require_tester(self, interaction: discord.Interaction) -> bool:
        if not has_tester_role(interaction.user, self.kit):
            role = interaction.guild.get_role(KITS[self.kit]["role"])
            role_display = role.name if role else "Specialized Tester"
            await interaction.response.send_message(f"❌ You need the **{role_display}** role to do that.", ephemeral=True)
            return False
        return True

    async def skip_callback(self, interaction: discord.Interaction):
        if not await self._require_tester(interaction):
            return
        await interaction.response.send_message("⏭️ Test marked as skipped. Closing this room in 5 seconds...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.HTTPException:
            pass

    async def close_callback(self, interaction: discord.Interaction):
        if not await self._require_tester(interaction):
            return
        await interaction.response.send_message("🔒 Closing this test room in 5 seconds...")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.HTTPException:
            pass


async def create_ticket_for(interaction: discord.Interaction, kit: str, player_data: dict):
    guild = interaction.guild
    try:
        # fetch_member asks Discord directly instead of relying on the bot's local member
        # cache, which is often incomplete without the (privileged) Members intent enabled —
        # that gap was causing "player is no longer in the server" for players who ARE still here.
        target_player = await guild.fetch_member(player_data["user_id"])
    except discord.NotFound:
        await interaction.followup.send("⚠️ That player is no longer in the server.", ephemeral=True)
        return None

    required_role = guild.get_role(KITS[kit]["role"])
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        target_player: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),  # ensures the bot can always post in tickets it creates
    }
    if required_role:
        overwrites[required_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    tier_tester_role = guild.get_role(TIER_TESTER_ROLE_ID)
    if tier_tester_role:
        overwrites[tier_tester_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    ticket_category = guild.get_channel(TICKET_CATEGORY_ID)
    ticket_channel = await guild.create_text_channel(
        name=f"{kit.lower().replace(' ', '-')}-{target_player.name}",
        category=ticket_category,
        overwrites=overwrites,
    )
    queues.record_ticket(ticket_channel.id, target_player.id, player_data["name_ans"], kit)
    try:
        await ticket_channel.send(
            f"🏁 {target_player.mention} welcome to your **{KITS[kit]['label']}** tier test room!\n"
            f"📋 **Name Provided:** `{player_data['name_ans']}`\n\n"
            f"Your assigned tester is {interaction.user.mention}.",
            view=TicketControlView(kit, ticket_channel.id),
        )
    except discord.Forbidden:
        await interaction.followup.send(
            f"⚠️ Ticket {ticket_channel.mention} was created, but I couldn't post the welcome message in it — "
            "check my permission overwrites in that channel.",
            ephemeral=True,
        )
    return ticket_channel


class QueueControlView(discord.ui.View):
    """The queue card's player-facing controls. Management actions (open ticket, lock,
    close, next, skip) are handled via slash commands instead of buttons here."""
    def __init__(self, kit: str):
        super().__init__(timeout=None)
        self.kit = kit

        self._add(discord.ButtonStyle.success, "Join Queue", "✅", 0, self.join_callback)
        self._add(discord.ButtonStyle.danger, "Leave Queue", "🚪", 0, self.leave_callback)

    def _add(self, style, label, emoji, row, callback):
        button = discord.ui.Button(style=style, label=label, emoji=emoji, row=row, custom_id=f"{label.lower().replace(' ', '_')}::{self.kit}")
        button.callback = callback
        self.add_item(button)

    async def _require_tester(self, interaction: discord.Interaction) -> bool:
        if not has_tester_role(interaction.user, self.kit):
            role = interaction.guild.get_role(KITS[self.kit]["role"])
            role_display = role.name if role else "Specialized Tester"
            await interaction.response.send_message(f"❌ You need the **{role_display}** role to do that.", ephemeral=True)
            return False
        return True

    async def join_callback(self, interaction: discord.Interaction):
        panel = queues.open_panels.get(self.kit)
        if panel and panel["locked"]:
            await interaction.response.send_message("🔒 This queue is currently locked and not accepting new joins.", ephemeral=True)
            return
        existing_kit = queues.already_queued(interaction.user.id)
        if existing_kit:
            await interaction.response.send_message(
                f"❌ You are already waiting in the **{KITS[existing_kit]['label']}** queue! Leave it first.", ephemeral=True
            )
            return
        remaining = queues.get_cooldown_remaining(interaction.user.id, self.kit)
        if remaining:
            await interaction.response.send_message(
                f"⏳ You're on cooldown for **{KITS[self.kit]['label']}** for another {format_duration(remaining)}.", ephemeral=True
            )
            return
        await interaction.response.send_modal(JoinQueueModal(self.kit))

    async def leave_callback(self, interaction: discord.Interaction):
        current_kit = queues.already_queued(interaction.user.id)
        if current_kit != self.kit:
            msg = "❌ You are not currently waiting in this queue." if current_kit is None else \
                  f"❌ You're queued in **{KITS[current_kit]['label']}**, not this one."
            await interaction.response.send_message(msg, ephemeral=True)
            return
        queues.leave(interaction.user.id)
        await interaction.response.edit_message(embed=build_queue_embed(self.kit), view=QueueControlView(self.kit))
        await interaction.followup.send("👋 You left the queue.", ephemeral=True)

    async def open_ticket_callback(self, interaction: discord.Interaction):
        if not await self._require_tester(interaction):
            return
        players = queues.queues.get(self.kit, [])
        if not players:
            await interaction.response.send_message(f"❌ No players are waiting in the **{KITS[self.kit]['label']}** queue.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        ticket_channel = await create_ticket_for(interaction, self.kit, players[0])
        if ticket_channel:
            queues.set_tester(self.kit, interaction.user.id)
            await interaction.followup.send(f"🎫 Ticket opened for **{players[0]['name_ans']}**: {ticket_channel.mention}", ephemeral=True)
            await refresh_panel_message(self.kit)

    async def lock_callback(self, interaction: discord.Interaction):
        if not await self._require_tester(interaction):
            return
        panel = queues.open_panels.get(self.kit)
        queues.set_locked(self.kit, not panel["locked"])
        await interaction.response.edit_message(embed=build_queue_embed(self.kit), view=QueueControlView(self.kit))

    async def close_callback(self, interaction: discord.Interaction):
        if not await self._require_tester(interaction):
            return
        for player in queues.queues.get(self.kit, []):
            queues.user_index.pop(player["user_id"], None)
        queues.queues[self.kit] = []
        queues.clear_panel(self.kit)
        await interaction.response.send_message(f"🔒 Closed the **{KITS[self.kit]['label']}** queue.", ephemeral=True)
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass

    async def next_callback(self, interaction: discord.Interaction):
        if not await self._require_tester(interaction):
            return
        player_data = queues.pop_next(self.kit)
        if not player_data:
            await interaction.response.send_message(f"❌ No players are waiting in the **{KITS[self.kit]['label']}** queue.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        ticket_channel = await create_ticket_for(interaction, self.kit, player_data)
        if ticket_channel:
            queues.set_tester(self.kit, interaction.user.id)
            await interaction.followup.send(f"✅ Pulled **{player_data['name_ans']}**. Ticket: {ticket_channel.mention}", ephemeral=True)
        await refresh_panel_message(self.kit)

    async def skip_callback(self, interaction: discord.Interaction):
        if not await self._require_tester(interaction):
            return
        player_data = queues.pop_next(self.kit)
        if not player_data:
            await interaction.response.send_message(f"❌ No players are waiting in the **{KITS[self.kit]['label']}** queue.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=build_queue_embed(self.kit), view=QueueControlView(self.kit))
        await interaction.followup.send(f"⏩ Skipped **{player_data['name_ans']}**.", ephemeral=True)


# ==================== BOT LIFECYCLE ====================
@bot.event
async def on_ready():
    print(f"🚀 Cozy SMP Waitlist Bot is online as {bot.user}")
    bot.add_view(WaitlistView())
    bot.add_view(NotificationView())

    # Re-register a persistent view for every kit panel that was open before the last restart,
    # so the buttons on old messages keep working instead of going dead.
    for kit in queues.open_panels:
        bot.add_view(QueueControlView(kit))

    try:
        guild = discord.Object(id=TEST_GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"⚙️ Slash commands synced to Guild ID: {TEST_GUILD_ID}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Without this, an exception inside any slash command just times out silently
    # as "The application did not respond" with no clue why. This prints the real
    # cause to your console AND tells the user something broke instead of nothing.
    print(f"[Command Error] /{interaction.command.name if interaction.command else '?'}: {error!r}")

    if isinstance(error, app_commands.CheckFailure):
        message = "❌ You need the **Tier Tester** role (or Administrator) to use this command."
    else:
        message = f"⚠️ Something went wrong running that command: `{error}`"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass  # interaction already expired, nothing more we can do


# ==================== SELF-SERVE PING NOTIFICATIONS ====================
class NotificationDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=info["label"], value=kit, description="Get pinged when this queue opens", emoji=info["emoji"])
            for kit, info in KITS.items()
        ]
        super().__init__(
            placeholder="Select your gamemode notification roles...",
            min_values=0,
            max_values=len(options),
            options=options,
            custom_id="notification_dropdown",
        )

    async def callback(self, interaction: discord.Interaction):
        selected = set(self.values)
        member = interaction.user
        added, removed, skipped = [], [], []

        for kit, info in KITS.items():
            role = interaction.guild.get_role(info["ping_role"])
            if role is None:
                continue
            has_role = role in member.roles
            wants_role = kit in selected
            try:
                if wants_role and not has_role:
                    await member.add_roles(role, reason="Self-serve tester notification opt-in")
                    added.append(info["label"])
                elif not wants_role and has_role:
                    await member.remove_roles(role, reason="Self-serve tester notification opt-out")
                    removed.append(info["label"])
            except discord.Forbidden:
                # Usually means the bot's role sits below the waitlist role in the role list
                skipped.append(info["label"])

        lines = []
        if added:
            lines.append("🔔 Subscribed: " + ", ".join(added))
        if removed:
            lines.append("🔕 Unsubscribed: " + ", ".join(removed))
        if skipped:
            lines.append("⚠️ Couldn't update: " + ", ".join(skipped) + " (ask an admin to move my role above these)")
        if not lines:
            lines.append("No changes made — your notification settings are unchanged.")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)


class NotificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(NotificationDropdown())


def create_notification_embed():
    embed = discord.Embed(
        title="🔔 Tier Test Notifications",
        description=(
            "A clean control panel for managing your ping notifications.\n"
            "Pick your gamemodes below to get notified the moment a queue opens for them.\n\n"
            "• Select the gamemodes you want to be notified for.\n"
            "↳ Get pinged the moment a queue opens.\n"
            "↳ Join before the queue fills up.\n"
            "↳ Uncheck anytime to unsubscribe."
        ),
        color=discord.Color.from_rgb(255, 140, 0),
    )
    return embed


# ==================== COMMANDS ====================
@bot.tree.command(name="setup_notifications", description="Posts the self-serve tester notification panel in this channel.")
@is_tier_tester()
async def setup_notifications(interaction: discord.Interaction):
    await interaction.response.send_message("Notification panel deployed.", ephemeral=True)
    await interaction.channel.send(embed=create_notification_embed(), view=NotificationView())


@bot.tree.command(name="setup_queue", description="Spawns the advanced kit structured waitlist panel.")
@is_tier_tester()
async def setup_queue(interaction: discord.Interaction):
    await interaction.response.send_message("Panel deployed successfully.", ephemeral=True)
    await interaction.channel.send(embed=create_cozy_embed(), view=WaitlistView())


@bot.tree.command(name="openqueue", description="Opens a queue card for a single gamemode in this channel.")
@app_commands.describe(gamemode="Which kit's queue to open")
@app_commands.choices(gamemode=KIT_CHOICES)
@is_tier_tester()
async def openqueue(interaction: discord.Interaction, gamemode: app_commands.Choice[str]):
    kit = gamemode.value
    channel_id = KITS[kit]["queue_channel"]
    target_channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
    if target_channel is None:
        await interaction.response.send_message(f"❌ Couldn't find the queue channel configured for **{KITS[kit]['label']}**.", ephemeral=True)
        return

    role = interaction.guild.get_role(KITS[kit]["ping_role"])
    ping_content = role.mention if role else None

    # Delete any leftover card from a previous session (e.g. a "no tester available" closed
    # card) so opening a queue never leaves stale messages piling up in the channel.
    old_message = queues.last_message.get(kit)
    if old_message:
        try:
            old_channel = bot.get_channel(old_message["channel_id"]) or await bot.fetch_channel(old_message["channel_id"])
            old_msg_obj = await old_channel.fetch_message(old_message["message_id"])
            await old_msg_obj.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

    # Register the panel state first so build_queue_embed() has something to read
    queues.set_panel(kit, target_channel.id, message_id=0, tester_id=interaction.user.id)
    view = QueueControlView(kit)
    bot.add_view(view)

    try:
        msg = await target_channel.send(
            content=ping_content,
            embed=build_queue_embed(kit),
            view=view,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
    except discord.Forbidden:
        queues.clear_panel(kit)
        await interaction.response.send_message(
            f"❌ I don't have access to {target_channel.mention} — check that I can View Channel and Send Messages there "
            "(channel-specific permission overrides can block a bot even if it has those permissions server-wide).",
            ephemeral=True,
        )
        return

    queues.open_panels[kit]["message_id"] = msg.id
    queues.save()
    queues.record_message(kit, target_channel.id, msg.id)
    await interaction.response.send_message(f"✅ Opened the **{KITS[kit]['label']}** queue in {target_channel.mention}.", ephemeral=True)


@bot.tree.command(name="closequeue", description="Closes the open queue card for a gamemode and clears its waitlist.")
@app_commands.describe(gamemode="Which kit's queue to close")
@app_commands.choices(gamemode=KIT_CHOICES)
@is_tier_tester()
async def closequeue(interaction: discord.Interaction, gamemode: app_commands.Choice[str]):
    kit = gamemode.value
    panel = queues.open_panels.get(kit)

    if panel:
        try:
            channel = bot.get_channel(panel["channel_id"]) or await bot.fetch_channel(panel["channel_id"])
            message = await channel.fetch_message(panel["message_id"])
            await message.edit(content=None, embed=build_closed_embed(kit), view=None)
            queues.record_message(kit, panel["channel_id"], panel["message_id"])
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"Couldn't update queue panel message on close: {e}")

    for player in queues.queues.get(kit, []):
        queues.user_index.pop(player["user_id"], None)
    queues.queues[kit] = []
    queues.record_close(kit)
    queues.clear_panel(kit)

    await interaction.response.send_message(f"🔒 Closed the **{KITS[kit]['label']}** queue and cleared its waitlist.", ephemeral=True)


async def _pull_next(interaction: discord.Interaction, kit: str, open_ticket: bool):
    if not has_tester_role(interaction.user, kit):
        role = interaction.guild.get_role(KITS[kit]["role"])
        role_display = role.name if role else "Specialized Tester"
        await interaction.response.send_message(f"❌ Access Denied: You need the **{role_display}** role for this.", ephemeral=True)
        return

    player_data = queues.pop_next(kit)
    if not player_data:
        await interaction.response.send_message(f"❌ No players are waiting in the **{KITS[kit]['label']}** queue.", ephemeral=True)
        return

    if not open_ticket:
        await interaction.response.send_message(f"⏩ Skipped **{player_data['name_ans']}** from the **{KITS[kit]['label']}** queue.", ephemeral=True)
        await refresh_panel_message(kit)
        return

    await interaction.response.defer(ephemeral=True)
    ticket_channel = await create_ticket_for(interaction, kit, player_data)
    if ticket_channel:
        queues.set_tester(kit, interaction.user.id)
        await interaction.followup.send(f"✅ Pulled **{player_data['name_ans']}**. Ticket opened: {ticket_channel.mention}", ephemeral=True)
    await refresh_panel_message(kit)


@bot.tree.command(name="next", description="Pulls the next player from a kit's queue and opens a test ticket.")
@app_commands.describe(gamemode="Which kit's queue to pull from")
@app_commands.choices(gamemode=KIT_CHOICES)
async def next_cmd(interaction: discord.Interaction, gamemode: app_commands.Choice[str]):
    await _pull_next(interaction, gamemode.value, open_ticket=True)


@bot.tree.command(name="skip", description="Removes the next player in a kit's queue without opening a ticket.")
@app_commands.describe(gamemode="Which kit's queue to skip in")
@app_commands.choices(gamemode=KIT_CHOICES)
async def skip(interaction: discord.Interaction, gamemode: app_commands.Choice[str]):
    await _pull_next(interaction, gamemode.value, open_ticket=False)


def get_current_tier(member: discord.Member, kit: str) -> str:
    """Looks at the member's actual roles to find which tier (if any) they currently hold
    for this kit. Returns 'N/A' if they don't have any tier role for it."""
    tier_map = KIT_TIER_ROLES.get(kit, {})
    member_role_ids = {r.id for r in member.roles}
    for tier, role_id in tier_map.items():
        if role_id is not None and role_id in member_role_ids:
            return tier
    return "N/A"


async def build_tierlist_content(guild: discord.Guild, kit: str) -> str:
    tier_map = KIT_TIER_ROLES.get(kit, {})
    role_to_tier = {role_id: tier for tier, role_id in tier_map.items() if role_id is not None}
    members_by_tier = {tier: [] for tier in TIERS}

    async for member in guild.fetch_members(limit=None):
        member_role_ids = {r.id for r in member.roles}
        for role_id, tier in role_to_tier.items():
            if role_id in member_role_ids:
                display = queues.get_ign(member.id) or member.display_name
                members_by_tier[tier].append(display)
                break  # a member should only hold one tier role per kit

    title = TIERLIST_CONFIG[kit]["title"]
    lines = [
        "╔══════════════════════════╗",
        f"✦ {to_bold_serif(title)} {to_bold_serif('LEADERBOARD')} ✦",
        "╚══════════════════════════╝",
    ]
    for tier in TIERS:
        emoji = TIER_EMOJIS[tier]
        bar = "━" * (17 if len(tier) == 1 else 16)
        lines.append(f"━━━ {emoji} {to_bold_sans(tier)} {bar}")
        for name in members_by_tier[tier]:
            lines.append(f"- {name}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    today = time.strftime("%B %d, %Y", time.gmtime())
    lines.append(f"📅 {to_bold_sans('Last Updated')}: {today}")
    return "\n".join(lines)


async def refresh_tierlist(guild: discord.Guild, kit: str):
    config = TIERLIST_CONFIG.get(kit)
    if config is None:
        return
    channel_id = config["channel"]
    channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
    if channel is None:
        return

    content = await build_tierlist_content(guild, kit)
    existing = queues.tierlist_message.get(kit)

    if existing:
        try:
            message = await channel.fetch_message(existing["message_id"])
            await message.edit(content=content)
            return
        except (discord.NotFound, discord.Forbidden):
            pass  # fall through and post a fresh one

    try:
        message = await channel.send(content)
        queues.record_tierlist_message(kit, channel_id, message.id)
    except discord.Forbidden:
        print(f"[Tierlist] Missing access to post in channel {channel_id} for {kit}")


async def apply_tier_role(guild: discord.Guild, member: discord.Member, kit: str, rank_earned: str) -> str:
    """Removes any tier role the member holds for this kit and gives them the new one.
    Returns a short status string to include in the tester's confirmation message."""
    tier_map = KIT_TIER_ROLES.get(kit, {})
    new_role_id = tier_map.get(rank_earned)

    if new_role_id is None:
        return f"⚠️ No tier roles are configured yet for **{KITS[kit]['label']}** — skipped the role update."

    # Remove whatever tier role (for this kit) the member currently holds, regardless of what
    # "previous_tier" was typed in — this stays correct even if that field is filled in wrong.
    kit_role_ids = {rid for rid in tier_map.values() if rid is not None}
    roles_to_remove = [r for r in member.roles if r.id in kit_role_ids and r.id != new_role_id]

    new_role = guild.get_role(new_role_id)
    if new_role is None:
        return f"⚠️ Couldn't find the **{rank_earned}** role for {KITS[kit]['label']} on this server (bad role ID?) — skipped."

    try:
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=f"Tier test result: {kit}")
        if new_role not in member.roles:
            await member.add_roles(new_role, reason=f"Tier test result: {kit}")
        return f"🏆 Gave {member.mention} the **{rank_earned}** role for {KITS[kit]['label']}."
    except discord.Forbidden:
        return "⚠️ I don't have permission to manage that role — make sure my role sits above the tier roles."


@bot.tree.command(name="result", description="Posts a tier test result. Run inside a test ticket to auto-fill the player.")
@app_commands.describe(
    score="Match score, e.g. 6-0",
    rank_earned="Tier awarded from this test",
    player="Only needed if NOT running this inside the player's ticket channel",
    username="Only needed if NOT running this inside the player's ticket channel",
    gamemode="Only needed if NOT running this inside the player's ticket channel",
)
@app_commands.choices(gamemode=KIT_CHOICES, rank_earned=TIER_CHOICES)
async def result(
    interaction: discord.Interaction,
    score: str,
    rank_earned: app_commands.Choice[str],
    player: discord.Member = None,
    username: str = None,
    gamemode: app_commands.Choice[str] = None,
):
    # Defer immediately — this command does several sequential API calls (posting the embed,
    # saving the cooldown, adding/removing tier roles) that together can exceed Discord's
    # 3-second reply window, which caused "Unknown interaction" errors. Deferring acknowledges
    # the interaction right away; everything else below replies via followup instead.
    await interaction.response.defer(ephemeral=True)

    # Auto-fill from the ticket this command was run in, if we recognize the channel
    ticket_info = queues.get_ticket_player(interaction.channel.id)

    kit = gamemode.value if gamemode else (ticket_info["kit"] if ticket_info else None)
    if kit is None:
        await interaction.followup.send(
            "❌ I can't tell which kit this is for. Run this inside the player's ticket channel, or specify `gamemode` manually.",
            ephemeral=True,
        )
        return

    if not has_tester_role(interaction.user, kit):
        role = interaction.guild.get_role(KITS[kit]["role"])
        role_display = role.name if role else "Specialized Tester"
        await interaction.followup.send(f"❌ Access Denied: You need the **{role_display}** role to post results for this kit.", ephemeral=True)
        return

    if player is None:
        if ticket_info is None:
            await interaction.followup.send(
                "❌ I couldn't find a player for this ticket. Run this inside the player's ticket channel, or specify `player` manually.",
                ephemeral=True,
            )
            return
        try:
            player = await interaction.guild.fetch_member(ticket_info["user_id"])
        except discord.NotFound:
            await interaction.followup.send("❌ That player is no longer in the server.", ephemeral=True)
            return

    if username is None:
        username = ticket_info["name_ans"] if ticket_info else player.display_name

    previous_tier_value = get_current_tier(player, kit)
    queues.set_ign(player.id, username)

    embed = discord.Embed(color=discord.Color.from_rgb(255, 140, 0))
    embed.set_author(name=f"{player.display_name}'s Test Results 🏆", icon_url=player.display_avatar.url)
    embed.add_field(name="Tester", value=interaction.user.mention, inline=False)
    embed.add_field(name="Kit", value=KITS[kit]["label"], inline=False)
    embed.add_field(name="Username", value=username, inline=False)
    embed.add_field(name="Score", value=score, inline=False)
    embed.add_field(name="Previous Tier", value=previous_tier_value, inline=False)
    embed.add_field(name="Rank Earned", value=f"**{rank_earned.value}**", inline=False)

    target_channel = interaction.channel
    if RESULTS_CHANNEL_ID:
        found = bot.get_channel(RESULTS_CHANNEL_ID)
        if found:
            target_channel = found

    # Content mention actually pings the player (mentions inside embeds alone won't notify)
    await target_channel.send(content=player.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
    queues.set_cooldown(player.id, kit)
    role_status = await apply_tier_role(interaction.guild, player, kit, rank_earned.value)
    if kit in TIERLIST_CONFIG:
        await refresh_tierlist(interaction.guild, kit)

    is_this_a_ticket = ticket_info is not None and ticket_info["user_id"] == player.id
    if is_this_a_ticket:
        confirmation = f"✅ Result posted{' in ' + target_channel.mention if target_channel.id != interaction.channel.id else ''}.\n{role_status}\n🗑️ Closing this ticket in 5 seconds..."
        await interaction.followup.send(confirmation, ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.HTTPException:
            pass
    else:
        confirmation = f"✅ Result posted{' in ' + target_channel.mention if target_channel.id != interaction.channel.id else ''}.\n{role_status}"
        await interaction.followup.send(confirmation, ephemeral=True)


@bot.tree.command(name="setign", description="Manually sets a member's IGN, used on the leaderboards.")
@app_commands.describe(member="Who to set the IGN for", ign="Their Minecraft username")
@is_tier_tester()
async def setign(interaction: discord.Interaction, member: discord.Member, ign: str):
    queues.set_ign(member.id, ign)
    await interaction.response.send_message(
        f"✅ Set {member.mention}'s IGN to `{ign}`. Run `/updatetierlist` on any kit they're ranked in to refresh it there.",
        ephemeral=True,
    )


@bot.tree.command(name="updatetierlist", description="Manually refreshes a kit's leaderboard channel.")
@app_commands.describe(gamemode="Which kit's leaderboard to refresh")
@app_commands.choices(gamemode=KIT_CHOICES)
@is_tier_tester()
async def updatetierlist(interaction: discord.Interaction, gamemode: app_commands.Choice[str]):
    kit = gamemode.value
    if kit not in TIERLIST_CONFIG:
        await interaction.response.send_message(f"❌ No leaderboard channel is configured for **{KITS[kit]['label']}**.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await refresh_tierlist(interaction.guild, kit)
    await interaction.followup.send(f"✅ Refreshed the **{KITS[kit]['label']}** leaderboard.", ephemeral=True)


@bot.tree.command(name="close_test", description="Closes and deletes the current tier testing channel room.")
async def close_test(interaction: discord.Interaction):
    if queues.get_ticket_player(interaction.channel.id) is None:
        await interaction.response.send_message(
            "❌ This command can only be used inside an active ticket channel created by the bot "
            "(a queue channel like #sword-queue is NOT a ticket, even if its name looks similar).",
            ephemeral=True,
        )
        return

    await interaction.response.send_message("⚙️ Closing test room channel in 5 seconds...")
    await asyncio.sleep(5)
    await interaction.channel.delete()


# ==================== BOT STARTUP ====================
if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("❌ DISCORD_TOKEN environment variable is not set!")
        print("Set it in Railway's Variables section (or your local environment).")
        exit(1)

    print("🤖 Starting Cozy Tiers bot...")
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
        raise
