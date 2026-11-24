# Beacon Discord Sync

Beacon Discord Sync is a small Windows companion tool for the [Beacon](https://github.com/drackdaddy/Beacon) addon for **World of Warcraft: Forever**. It reads your Discord server's members and roles with your own Discord bot and turns them into Beacon aliases, so you don't have to look up Discord IDs by hand. The addon can't connect to Discord itself, so this tool runs outside the game.

It's a separate download from Beacon. Keep it in its own folder, not inside the Beacon addon folder, because updating Beacon replaces that folder.

## Download

On this page, choose **Code → Download ZIP** and unzip it anywhere you like, for example in your Documents folder. You need Windows 10 or 11.

## Set up the bot (one time)

1. Go to <https://discord.com/developers/applications>, choose **New Application**, name it (for example `Beacon Export`) and choose **Create**.
2. Open **Bot**, choose **Reset Token** and copy the token. Treat it like a password.
3. On the same page, under **Privileged Gateway Intents**, turn on **Server Members Intent** and save.
4. Open **OAuth2 → URL Generator**, tick **bot**, then under **Bot Permissions** tick **View Channels** and **Send Messages**. Also tick **Send Messages in Threads** if you'll post to a forum post or thread. Open the generated link and add the bot to your server.

If you'll post to a private channel, also allow the bot **View Channel** and **Send Messages** there.

## Run it

Double-click `BeaconDiscordExport.bat`. The first time, it installs Python and the parts it needs if they're missing, then asks:

1. **Your bot token.** It's stored in Windows Credential Manager, never in a file.
2. **Where the export should go:**
   - **Straight into Beacon in game.** It writes `DiscordExportData.lua` into the Beacon folder. In game, type `/reload` and choose **Personal**, or **Guild** if you're an officer. The game can stay open.
   - **Post in a Discord channel**, as code blocks. Paste them into **Import...** in Beacon. For a big server, paste **all the parts together** so Beacon can also remove people who left.
   - **Both.**
3. **The channel link**, if you post to a channel. Right-click the channel and choose **Copy Link**.
4. **Whether to include Discord roles**, for aliases like `@raidteam`.
5. **Where Beacon is installed**, if the export goes into Beacon. Paste the path of the folder that holds `Beacon.toc`, for example `...\World of Warcraft\<your game version>\Interface\AddOns\Beacon`.

Later runs reuse your answers. Press **Enter** to export, or type **C** to change them. `/beacon discord` shows the import prompt again in game.

Updating Beacon replaces `DiscordExportData.lua`, so run the tool again after an update if you want to import a fresh export.

## What Beacon does with the export

When you import the export into a list, Beacon matches everyone by Discord ID:

- **New people and roles** are added. If an alias is already taken, a number is added, for example `@dark2`.
- **Nickname changes** update the display name. Everyone keeps the `@alias` they already use.
- **People who left the server, or roles that were deleted,** are removed from that list.

## How names become aliases

Names are cleaned up so they can be typed in game: accents and fancy letters become plain letters, and emoji and symbols are dropped. The alias is the cleaned name in lower case without spaces, for example **Dark Knight** becomes `@darkknight`. Names with no usable letters are skipped and listed when the tool finishes.

## Troubleshooting

| Message | Fix |
|---|---|
| `Discord rejected the bot token` | Reset the token in the Developer Portal and run the tool again to paste the new one. |
| `turn on 'Server Members Intent'` | Do step 3 of the bot setup. |
| `the bot can't see that server` | Add the bot to your server, or copy the channel link again. |
| `channel not found` / `can't see that channel` / `isn't allowed to post` | Copy the link again, or give the bot **View Channel** and **Send Messages** in that channel. |
| `Python was installed but could not be found` | Close the window and run the tool again. |
| `Beacon.toc isn't in that folder` | Paste the path of the `Beacon` folder inside `Interface\AddOns`, not the AddOns folder itself. |

The export holds everyone's display name and Discord ID, so post it only where your members or officers can see it.

## Credits

Beacon Discord Sync is free and is not affiliated with Discord or Blizzard Entertainment.

This tool was made with the assistance of AI.
