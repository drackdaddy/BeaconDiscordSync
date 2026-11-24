# Beacon Discord export (companion tool)
#
# Reads your Discord server's members and roles with your own Discord bot and
# turns them into Beacon aliases, one per line:
#
#   raidteam, Role, 123456789012345678, Raid Team
#   elara, Person, 234567890123456789, Elara
#
# Then, depending on what you choose:
#   * Straight into Beacon: writes DiscordExportData.lua in the Beacon addon
#     folder. Type /reload in game and Beacon offers to import it.
#   * Discord channel: posts it in a channel as code blocks that can be pasted
#     into Beacon's Import window.
#
# Run BeaconDiscordExport.bat. The first run asks for your bot token (kept in
# Windows Credential Manager, never in a file), where the export should go and,
# for the game, where Beacon is installed. Later runs reuse those settings;
# type C at the prompt to change them.

import getpass
import json
import os
import re
import sys
import time
import unicodedata

import discord
import keyring

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(HERE, "settings.json")
KEYRING_SERVICE = "Beacon Discord Export"
KEYRING_USER = "bot-token"
DATA_FILE_NAME = "DiscordExportData.lua"
MAX_POST = 2000        # Discord's message length limit
MAX_ALIAS = 24         # Beacon's alias limit
MAX_NAME = 32          # Beacon's display name limit
OUTPUTS = {"1": "game", "2": "channel", "3": "both"}
OUTPUT_NAMES = {"game": "Straight into Beacon in game", "channel": "Post in a Discord channel",
                "both": "Both: into Beacon and a Discord channel"}
CHANNEL_PATTERN = re.compile(r"/channels/(\d+)/(\d+)")


# ----------------------------------------------------------------------------
# Settings and prompts
# ----------------------------------------------------------------------------

def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def ask(prompt, default=None):
    """Asks a question; pressing Enter keeps the default."""
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or (default or "")


def ask_yes_no(prompt, default=True):
    answer = input(f"{prompt} ({'Y/n' if default else 'y/N'}): ").strip().lower()
    return default if not answer else answer.startswith("y")


def ask_token():
    """Asks for the bot token and stores it in Windows Credential Manager."""
    print()
    print("Paste your bot token (Developer Portal > your app > Bot > Reset Token).")
    print("Nothing shows while you paste; that's normal. Press Enter when done.")
    token = getpass.getpass("Bot token: ").strip()
    if not token:
        sys.exit("ERROR: no bot token entered.")
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)
    print("Saved in Windows Credential Manager.")
    return token


def find_beacon_folder(settings):
    """Returns the Beacon addon folder: the saved one, else asks for it."""
    saved = settings.get("beacon_folder")
    if saved and os.path.isfile(os.path.join(saved, "Beacon.toc")):
        return saved
    print()
    print("Where is Beacon installed? Paste the path of the folder that holds Beacon.toc,")
    print(r"for example ...\World of Warcraft\<your game version>\Interface\AddOns\Beacon")
    while True:
        folder = ask("Beacon folder", saved).strip('"')
        if os.path.isfile(os.path.join(folder, "Beacon.toc")):
            return folder
        print("Beacon.toc isn't in that folder. Try again.")


def setup(settings, token):
    """Asks for every setting. Returns the bot token."""
    if not token or not ask_yes_no("Keep the saved bot token?", True):
        token = ask_token()

    print()
    print("Where should the export go?")
    for key, value in OUTPUTS.items():
        print(f"  {key}) {OUTPUT_NAMES[value]}")
    default = next((k for k, v in OUTPUTS.items() if v == settings.get("output")), "1")
    while True:
        choice = ask("Choose 1, 2 or 3", default)
        if choice in OUTPUTS:
            settings["output"] = OUTPUTS[choice]
            break

    if settings["output"] in ("channel", "both"):
        print()
        print("Right-click the channel (or forum post) in Discord and choose Copy Link.")
        while True:
            link = ask("Channel link", settings.get("channel_link"))
            if CHANNEL_PATTERN.search(link):
                settings["channel_link"] = link
                break
            print("That isn't a channel link. It looks like https://discord.com/channels/<number>/<number>")
    # Which server to read comes from the channel link, or is asked after connecting.
    settings.pop("server_id", None)

    print()
    settings["include_roles"] = ask_yes_no("Include Discord roles, for aliases like @raid?",
                                           settings.get("include_roles", True))
    if settings["output"] in ("game", "both"):
        settings["beacon_folder"] = find_beacon_folder(settings)
    return token


def show_settings(settings):
    print("Saved settings:")
    print(f"  Bot token:     saved in Windows Credential Manager")
    print(f"  Export goes:   {OUTPUT_NAMES[settings['output']]}")
    if settings["output"] in ("channel", "both"):
        print(f"  Channel:       {settings.get('channel_link')}")
    if settings["output"] in ("game", "both"):
        print(f"  Beacon folder: {find_beacon_folder(settings)}")
    print(f"  Roles:         {'included' if settings.get('include_roles', True) else 'not included'}")


# ----------------------------------------------------------------------------
# Building the export
# ----------------------------------------------------------------------------

def normalize(name):
    """Turns a Discord name into plain ASCII text that Beacon and WoW chat accept."""
    text = unicodedata.normalize("NFKC", name)          # fancy/styled letters -> normal letters
    text = unicodedata.normalize("NFKD", text)          # split accents off letters
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.encode("ascii", "ignore").decode()      # drop emoji and anything non-ASCII
    text = re.sub(r"[,;|`#\t]", " ", text)              # separators in Beacon's format, WoW chat and code blocks
    return re.sub(r"\s+", " ", text).strip()[:MAX_NAME].strip()


def make_alias(name):
    """The alias typed after @: the name's letters, digits and underscores, in lower case."""
    return re.sub(r"[^a-z0-9_]", "", name.lower())[:MAX_ALIAS]


def unique_alias(base, used):
    """Adds a number (dark2, dark3...) when base is already taken in this export."""
    if base not in used:
        return base
    n = 2
    while True:
        candidate = base[:MAX_ALIAS - len(str(n))] + str(n)
        if candidate not in used:
            return candidate
        n += 1


def build_entries(people, roles):
    """people: (id, [names to try in order]); roles: (id, name).
    Returns entries (alias, kind, id, name) and the skipped ones' reasons."""
    entries, skipped, used = [], [], set()

    def add(kind, ident, names):
        name = next((n for n in map(normalize, names) if n), "")
        alias = make_alias(name)
        if not alias:
            skipped.append(f"{kind} {ident}: the name has no usable letters or digits")
            return
        alias = unique_alias(alias, used)
        used.add(alias)
        entries.append((alias, kind, str(ident), name))

    def sort_name(names):
        return next((n for n in map(normalize, names) if n), "").lower()

    for ident, name in sorted(roles, key=lambda r: sort_name([r[1]])):
        add("Role", ident, [name])
    for ident, names in sorted(people, key=lambda p: sort_name(p[1])):
        add("Person", ident, names)
    return entries, skipped


def entry_line(entry):
    return ", ".join(entry)


def header(stamp, part, total, server):
    # Beacon reads this line to know the export is complete, so it can remove
    # people who are no longer in the server.
    return f"# Beacon Discord export {stamp} part {part} of {total} ({server})"


def build_posts(entries, stamp, server):
    """Splits the export into Discord messages under 2,000 characters. Each one
    is a code block with its own header line."""
    title_room = len("**Beacon import** - part 99 of 99 - 9999 entries - updated <t:0000000000:f>"
                     " - paste all parts together\n```\n\n```") + len(header(stamp, 99, 99, server)) + 2
    budget = MAX_POST - title_room
    chunks, current, size = [], [], 0
    for entry in entries:
        line = entry_line(entry)
        if current and size + len(line) + 1 > budget:
            chunks.append(current)
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append(current)
    posts = []
    for i, chunk in enumerate(chunks, 1):
        part = f" - part {i} of {len(chunks)}" if len(chunks) > 1 else ""
        together = " - paste all parts together" if len(chunks) > 1 else ""
        posts.append(f"**Beacon import**{part} - {len(chunk)} entries - updated <t:{stamp}:f>{together}\n"
                     f"```\n{header(stamp, i, len(chunks), server)}\n" + "\n".join(chunk) + "\n```")
    return posts


def lua_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def write_data_file(folder, entries, stamp, server):
    """Writes DiscordExportData.lua for Beacon to read on the next /reload."""
    people = sum(1 for e in entries if e[1] == "Person")
    text = "\n".join([header(stamp, 1, 1, server)] + [entry_line(e) for e in entries])
    content = (
        "-- Beacon Discord export data, written by the companion tool "
        f"on {time.strftime('%Y-%m-%d %H:%M', time.localtime(stamp))}.\n"
        "-- Type /reload in game and Beacon offers to import it. Don't edit this file by hand.\n"
        "local _, ns = ...\n"
        "ns.discordExport = {\n"
        f"\ttime = {stamp},\n"
        f"\tserver = {lua_string(server)},\n"
        f"\tmembers = {people},\n"
        f"\troles = {len(entries) - people},\n"
        f"\ttext = {lua_string(text)},\n"
        "}\n"
    )
    path = os.path.join(folder, DATA_FILE_NAME)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.replace(temporary, path)
    return path


# ----------------------------------------------------------------------------
# Talking to Discord
# ----------------------------------------------------------------------------

def choose_server(client, settings):
    """Finds the server to read: from the channel link, the saved choice, the
    only server the bot is in, or by asking."""
    link = CHANNEL_PATTERN.search(settings.get("channel_link") or "") if settings["output"] != "game" else None
    server_id = int(link.group(1)) if link else settings.get("server_id")
    if server_id:
        server = client.get_guild(int(server_id))
        if server is None:
            print("ERROR: the bot can't see that server. Check the channel link and that the bot was invited.")
        return server
    servers = sorted(client.guilds, key=lambda g: g.name.lower())
    if not servers:
        print("ERROR: the bot isn't in any server yet. Invite it first (see the README).")
        return None
    if len(servers) == 1:
        server = servers[0]
    else:
        print()
        print("The bot is in more than one server. Which one should be exported?")
        for i, g in enumerate(servers, 1):
            print(f"  {i}) {g.name}")
        while True:
            choice = ask("Server number")
            if choice.isdigit() and 1 <= int(choice) <= len(servers):
                server = servers[int(choice) - 1]
                break
    settings["server_id"] = server.id
    save_settings(settings)
    return server


async def find_channel(client, settings):
    """Returns the channel to post in, or None after printing why it can't be used."""
    channel_id = int(CHANNEL_PATTERN.search(settings["channel_link"]).group(2))
    try:
        channel = await client.fetch_channel(channel_id)
    except discord.NotFound:
        print("ERROR: channel not found. Copy the channel link again.")
        return None
    except discord.Forbidden:
        print("ERROR: the bot can't see that channel. Give it View Channel there (see the README).")
        return None
    if not hasattr(channel, "send"):
        print("ERROR: the link points to a channel the bot can't post in (e.g. a forum or category). "
              "Link a text channel or a forum post instead.")
        return None
    return channel


def run_export(token, settings):
    intents = discord.Intents.default()
    intents.members = True  # needs "Server Members Intent" turned on in the Developer Portal
    client = discord.Client(intents=intents)
    result = {"ok": False}

    @client.event
    async def on_ready():
        try:
            server = choose_server(client, settings)
            if server is None:
                return
            channel = None
            if settings["output"] in ("channel", "both"):
                channel = await find_channel(client, settings)
                if channel is None:
                    return

            print(f"Reading members and roles of {server.name}...")
            people = [(m.id, [m.display_name, m.global_name or "", m.name])
                      async for m in server.fetch_members(limit=None) if not m.bot]
            roles = []
            if settings.get("include_roles", True):
                # Leave out @everyone and roles that belong to bots or integrations.
                roles = [(r.id, r.name) for r in server.roles if not r.is_default() and not r.managed]
            entries, skipped = build_entries(people, roles)
            if not entries:
                print("ERROR: nothing to export.")
                return

            stamp = int(time.time())
            server_name = normalize(server.name) or "your server"
            people_count = sum(1 for e in entries if e[1] == "Person")
            print(f"Exported {people_count} people and {len(entries) - people_count} roles.")

            if settings["output"] in ("game", "both"):
                path = write_data_file(settings["beacon_folder"], entries, stamp, server_name)
                print(f"Written to {path}")
                print("In game, type /reload and choose which list to import it into.")
                print("(If Beacon was just updated with new files, restart the game once instead.)")
            if channel is not None:
                posts = build_posts(entries, stamp, server_name)
                try:
                    for post in posts:
                        await channel.send(post, allowed_mentions=discord.AllowedMentions.none())
                except discord.Forbidden:
                    print("ERROR: the bot isn't allowed to post in that channel. "
                          "Give it Send Messages there (see the README).")
                    return
                print(f"Posted in {len(posts)} message(s) to {settings['channel_link']}")

            if skipped:
                print(f"\nSkipped {len(skipped)}:")
                for reason in skipped:
                    print("  - " + reason)
            result["ok"] = True
        finally:
            await client.close()

    try:
        client.run(token, log_handler=None)
    except discord.LoginFailure:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
        sys.exit("ERROR: Discord rejected the bot token, so it was removed. "
                 "Reset it in the Developer Portal and run this again to paste the new one.")
    except discord.PrivilegedIntentsRequired:
        sys.exit("ERROR: turn on 'Server Members Intent' under Bot in the Developer Portal, then run again.")
    return result["ok"]


def main():
    print("Beacon Discord export")
    print("=====================")
    settings = load_settings()
    token = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    if token and settings.get("output"):
        show_settings(settings)
        print()
        if input("Press Enter to export, or type C to change settings: ").strip().lower().startswith("c"):
            token = setup(settings, token)
    else:
        print("First run: let's set things up. You can change these later.")
        token = setup(settings, token)
    save_settings(settings)
    print()
    sys.exit(0 if run_export(token, settings) else 2)


if __name__ == "__main__":
    main()
