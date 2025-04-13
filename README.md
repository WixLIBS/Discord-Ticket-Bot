# /dazes Discord Ticket Bot

A powerful and modular Discord ticket bot with a clean UI and beautiful embeds for handling support tickets in your server.

## Features

- **Clean UI with Embeds**: Professional looking ticket system with embeds and buttons
- **Multiple Ticket Types**: Support for different ticket categories (general support, account issues, bug reports, etc.)
- **Ticket Management**: Open, close, delete, and reopen tickets
- **Staff Tools**: Claim tickets, export transcripts, view ticket statistics
- **Customizable**: Easy configuration for roles, channels, colors, and more
- **Modular Structure**: Uses cogs for clean and organized code

## Setup

1. Clone this repository
2. Install required dependencies:
   ```
   pip install discord.py
   ```
3. Configure your bot:
   - Add your bot token to `bot.py`
   - Run the bot and use the configuration commands to set up categories, channels, and roles

## Configuration

The bot uses a configuration system to store settings. Use the following commands to configure the bot:

- `!config` - View current configuration
- `!config help` - Show all configuration commands
- `!config category <category_id>` - Set ticket category
- `!config log <channel_id>` - Set log channel
- `!config addrole <role_id>` - Add a support role
- `!config removerole <role_id>` - Remove a support role
- `!config servername <name>` - Set server name (default: /dazes)
- `!config addtype <label> <emoji> <value>` - Add ticket type
- `!config removetype <value>` - Remove ticket type

## Commands

### Admin Commands
- `!setup` - Create the ticket panel with buttons
- `!stats` - Show basic ticket statistics
- `!ticketstats` - Show detailed ticket statistics
- `!tickets` - List all active tickets
- `!closeinactive [days]` - Close tickets inactive for specified days
- `!export [channel_id]` - Export ticket transcript

### Ticket Actions (Buttons)
- Create Ticket - Opens ticket type selection
- Close Ticket - Closes an open ticket
- Delete Ticket - Permanently deletes a closed ticket
- Reopen Ticket - Reopens a closed ticket
- Claim Ticket - Support staff can claim a ticket to handle it

## File Structure

```
├── bot.py                # Main bot file
├── config.json           # Bot configuration
├── tickets.json          # Ticket data storage
└── cogs/
    ├── tickets.py        # Ticket system functionality
    ├── config.py         # Configuration management
    └── utils.py          # Utility commands
```

## Support

If you need help with the bot, open a ticket in the /dazes Discord server!
