# MKVToolNix Telegram Bot

A feature-rich Telegram bot wrapper for MKVToolNix (mkvmerge, mkvextract, mkvinfo) with intuitive button-based interaction.

![Bot Demo](https://i.imgur.com/JQ7Z8lG.png) *(Example screenshot placeholder)*

## 🌟 Features

- **Full MKVToolNix Integration**:
  - Extract tracks from MKV files
  - Mux (combine) multiple files
  - Merge (append) files
  - Edit metadata (title, language, etc.)
  
- **Smart Features**:
  - Auto language detection from filenames
  - Progress tracking with speed indicators
  - Session management per user
  - Supports all MKVToolNix compatible formats

- **User-Friendly Interface**:
  - Button-based interaction
  - Guided workflows
  - Real-time feedback

## 🛠️ Installation

### Prerequisites
- Python 3.10+
- MKVToolNix installed (`mkvmerge`, `mkvextract`, `mkvinfo`)
- FFmpeg (optional, for fallback operations)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Docker (Recommended)
```bash
docker build -t mkvtoolnix-bot .
docker run -d --name mkvtoolnix-bot -e BOT_TOKEN=your_token_here mkvtoolnix-bot


Manual Setup
Clone the repository:

bash
git clone https://github.com/thecidkagenou/mkvtoolnix-bot.git
cd mkvtoolnix-bot
Install dependencies:

bash
pip install -r requirements.txt
Create .env file:

ini
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
BOT_TOKEN=your_bot_token
MAX_FILE_SIZE=2000000000  # 2GB in bytes
Run the bot:

bash
python bot.py
📚 Usage
Start the bot: /start

Send a media file (video/audio/subtitle)

Choose an action from the buttons:

Extract Tracks

Mux Files

Merge Files

Edit Metadata

Follow the interactive prompts

Commands:

/start - Show welcome message

/cancel - Cancel current operation

/reset - Reset your session
