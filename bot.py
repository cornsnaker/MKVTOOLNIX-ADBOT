import os
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, InputMediaDocument
)
from pyrogram.errors import (
    RPCError, MessageNotModified, MessageIdInvalid
)
import aiofiles
import psutil
from tqdm import tqdm

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 2000000000))  # 2GB
SUPPORTED_EXTENSIONS = {
    'video': ['.mkv', '.mp4', '.avi', '.webm', '.mov'],
    'audio': ['.aac', '.ac3', '.dts', '.mp3', '.opus', '.flac', '.wav'],
    'subtitles': ['.srt', '.ass', '.ssa', '.vtt', '.pgs', '.sub']
}
LANGUAGE_CODES = {
    'hi': ['hi', 'hin', 'hindi'],
    'en': ['en', 'eng', 'english'],
    'ta': ['ta', 'tam', 'tamil'],
    'bn': ['bn', 'ben', 'bengali'],
    'mr': ['mr', 'mar', 'marathi'],
    'gu': ['gu', 'guj', 'gujarati'],
    'kn': ['kn', 'kan', 'kannada'],
    'ml': ['ml', 'mal', 'malayalam'],
    'te': ['te', 'tel', 'telugu'],
    'pa': ['pa', 'pan', 'punjabi'],
    'or': ['or', 'ori', 'odia'],
    'as': ['as', 'asm', 'assamese'],
    'ne': ['ne', 'nep', 'nepali'],
    'sa': ['sa', 'san', 'sanskrit'],
    'ur': ['ur', 'urd', 'urdu']
}

# User session management
user_sessions: Dict[int, Dict] = {}

class MKVToolNixBot:
    def __init__(self):
        self.app = Client(
            "mkvtoolnix_bot",
            api_id=os.getenv("API_ID"),
            api_hash=os.getenv("API_HASH"),
            bot_token=os.getenv("BOT_TOKEN")
        )
        
        # Register handlers
        self.register_handlers()
    
    def run(self):
        self.app.run()
    
    def register_handlers(self):
        # Message handlers
        self.app.on_message(filters.document | filters.video | filters.audio)(self.handle_file_input)
        self.app.on_callback_query()(self.handle_callback_query)
        
        # Command handlers
        self.app.on_message(filters.command("start"))(self.handle_start)
        self.app.on_message(filters.command("cancel"))(self.handle_cancel)
        self.app.on_message(filters.command("reset"))(self.handle_reset)
    
    async def handle_start(self, client: Client, message: Message):
        """Handle /start command"""
        await message.reply_text(
            "👋 Welcome to MKVToolNix Bot!\n\n"
            "Send me an MKV or media file to get started. I can:\n"
            "- Extract tracks from MKV files\n"
            "- Mux (combine) multiple files\n"
            "- Merge (append) multiple files\n"
            "- Edit metadata (title, language, etc.)\n"
            "- Add subtitles to videos\n\n"
            "Supported formats:\n"
            "- Video: MKV, MP4, AVI, WebM\n"
            "- Audio: AAC, AC3, DTS, MP3, Opus\n"
            "- Subtitles: SRT, ASS, SSA, VTT, PGS"
        )
    
    async def handle_cancel(self, client: Client, message: Message):
        """Handle /cancel command"""
        user_id = message.from_user.id
        if user_id in user_sessions:
            del user_sessions[user_id]
            await message.reply_text("✅ Current operation cancelled. You can start a new one.")
        else:
            await message.reply_text("No active operation to cancel.")
    
    async def handle_reset(self, client: Client, message: Message):
        """Handle /reset command"""
        user_id = message.from_user.id
        if user_id in user_sessions:
            del user_sessions[user_id]
            await message.reply_text("✅ Session reset. You can start fresh now.")
        else:
            await message.reply_text("No active session to reset.")
    
    async def handle_file_input(self, client: Client, message: Message):
        """Handle incoming files"""
        user_id = message.from_user.id
        
        # Check if file is too large
        if message.document and message.document.file_size > MAX_FILE_SIZE:
            await message.reply_text(
                f"⚠️ File is too large! Max size is {MAX_FILE_SIZE // 1000000}MB."
            )
            return
        
        # Get file extension
        file_name = message.document.file_name if message.document else (
            message.video.file_name if message.video else (
                message.audio.file_name if message.audio else None
            )
        )
        
        if not file_name:
            await message.reply_text("⚠️ Could not determine file name.")
            return
        
        file_ext = Path(file_name).suffix.lower()
        
        # Check if file type is supported
        supported = False
        file_type = None
        for typ, exts in SUPPORTED_EXTENSIONS.items():
            if file_ext in exts:
                supported = True
                file_type = typ
                break
        
        if not supported:
            await message.reply_text(
                f"⚠️ Unsupported file type: {file_ext}\n\n"
                "Supported formats:\n"
                "- Video: MKV, MP4, AVI, WebM\n"
                "- Audio: AAC, AC3, DTS, MP3, Opus\n"
                "- Subtitles: SRT, ASS, SSA, VTT, PGS"
            )
            return
        
        # Initialize user session if not exists
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                'files': [],
                'current_operation': None,
                'processing': False
            }
        
        # Add file to user session
        user_sessions[user_id]['files'].append({
            'message': message,
            'file_name': file_name,
            'file_type': file_type,
            'file_ext': file_ext,
            'language': self.detect_language(file_name)
        })
        
        # Show action buttons
        await self.show_action_buttons(message, user_id)
    
    async def show_action_buttons(self, message: Message, user_id: int):
        """Show action selection buttons"""
        session = user_sessions[user_id]
        files = session['files']
        
        # Determine available actions based on file types
        buttons = []
        
        if len(files) == 1:
            if files[0]['file_type'] == 'video':
                buttons.append([
                    InlineKeyboardButton("Extract Tracks", callback_data="extract_tracks")
                ])
                buttons.append([
                    InlineKeyboardButton("Add/Edit Metadata", callback_data="edit_metadata")
                ])
            buttons.append([
                InlineKeyboardButton("Mux (Combine Files)", callback_data="mux_files")
            ])
            buttons.append([
                InlineKeyboardButton("Merge (Append Files)", callback_data="merge_files")
            ])
        else:
            # Multiple files - prioritize muxing/merging
            buttons.append([
                InlineKeyboardButton("Mux (Combine Files)", callback_data="mux_files")
            ])
            buttons.append([
                InlineKeyboardButton("Merge (Append Files)", callback_data="merge_files")
            ])
        
        # Common buttons
        buttons.append([
            InlineKeyboardButton("Add Another File", callback_data="add_another_file"),
            InlineKeyboardButton("View Added Files", callback_data="view_files")
        ])
        buttons.append([
            InlineKeyboardButton("Remove Last File", callback_data="remove_last_file"),
            InlineKeyboardButton("Cancel", callback_data="cancel_operation")
        ])
        
        await message.reply_text(
            "📁 Choose an action:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def handle_callback_query(self, client: Client, callback_query: CallbackQuery):
        """Handle all callback queries"""
        user_id = callback_query.from_user.id
        data = callback_query.data
        
        try:
            if user_id not in user_sessions:
                await callback_query.answer("Session expired. Please send a file again.")
                return
            
            if data == "extract_tracks":
                await self.handle_extract_tracks(callback_query)
            elif data == "mux_files":
                await self.handle_mux_files(callback_query)
            elif data == "merge_files":
                await self.handle_merge_files(callback_query)
            elif data == "edit_metadata":
                await self.handle_edit_metadata(callback_query)
            elif data == "add_another_file":
                await callback_query.answer("Please send the next file.")
            elif data == "view_files":
                await self.show_added_files(callback_query)
            elif data == "remove_last_file":
                await self.remove_last_file(callback_query)
            elif data == "cancel_operation":
                del user_sessions[user_id]
                await callback_query.message.edit_text("Operation cancelled.")
            else:
                await callback_query.answer("Unknown action.")
        
        except Exception as e:
            logger.error(f"Error in callback handler: {e}", exc_info=True)
            await callback_query.answer("An error occurred. Please try again.")
    
    async def handle_extract_tracks(self, callback_query: CallbackQuery):
        """Handle extract tracks operation"""
        user_id = callback_query.from_user.id
        session = user_sessions[user_id]
        
        if len(session['files']) != 1 or session['files'][0]['file_type'] != 'video':
            await callback_query.answer("Please send a single video file first.")
            return
        
        session['current_operation'] = 'extract_tracks'
        
        # Get file info
        message = session['files'][0]['message']
        file_path = await self.download_file(message)
        
        # Get tracks info using mkvinfo
        tracks = await self.get_mkv_tracks(file_path)
        
        # Show tracks selection
        buttons = []
        for track in tracks:
            buttons.append([
                InlineKeyboardButton(
                    f"{track['type'].capitalize()} {track['id']}: {track.get('codec', '')} "
                    f"{track.get('language', '')}",
                    callback_data=f"extract_track_{track['id']}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton("Extract All", callback_data="extract_all_tracks"),
            InlineKeyboardButton("Cancel", callback_data="cancel_operation")
        ])
        
        await callback_query.message.edit_text(
            "Select tracks to extract:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def handle_mux_files(self, callback_query: CallbackQuery):
        """Handle mux files operation"""
        user_id = callback_query.from_user.id
        session = user_sessions[user_id]
        
        if len(session['files']) < 2:
            await callback_query.answer("Please send at least 2 files to mux.")
            return
        
        session['current_operation'] = 'mux_files'
        
        # Show mux options
        buttons = [
            [
                InlineKeyboardButton("Set Output Title", callback_data="set_output_title"),
                InlineKeyboardButton("Set Track Names", callback_data="set_track_names")
            ],
            [
                InlineKeyboardButton("Set Languages", callback_data="set_languages"),
                InlineKeyboardButton("Set Default/Forced", callback_data="set_default_forced")
            ],
            [
                InlineKeyboardButton("Start Muxing", callback_data="start_muxing"),
                InlineKeyboardButton("Cancel", callback_data="cancel_operation")
            ]
        ]
        
        await callback_query.message.edit_text(
            "Configure muxing options:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def handle_merge_files(self, callback_query: CallbackQuery):
        """Handle merge files operation"""
        user_id = callback_query.from_user.id
        session = user_sessions[user_id]
        
        if len(session['files']) < 2:
            await callback_query.answer("Please send at least 2 files to merge.")
            return
        
        session['current_operation'] = 'merge_files'
        
        # Show merge options
        buttons = [
            [
                InlineKeyboardButton("Set Output Title", callback_data="set_output_title"),
                InlineKeyboardButton("Set Track Names", callback_data="set_track_names")
            ],
            [
                InlineKeyboardButton("Start Merging", callback_data="start_merging"),
                InlineKeyboardButton("Cancel", callback_data="cancel_operation")
            ]
        ]
        
        await callback_query.message.edit_text(
            "Configure merging options:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def handle_edit_metadata(self, callback_query: CallbackQuery):
        """Handle edit metadata operation"""
        user_id = callback_query.from_user.id
        session = user_sessions[user_id]
        
        if len(session['files']) != 1 or session['files'][0]['file_type'] != 'video':
            await callback_query.answer("Please send a single video file first.")
            return
        
        session['current_operation'] = 'edit_metadata'
        
        # Show metadata options
        buttons = [
            [
                InlineKeyboardButton("Change Title", callback_data="change_title"),
                InlineKeyboardButton("Change Track Names", callback_data="change_track_names")
            ],
            [
                InlineKeyboardButton("Change Languages", callback_data="change_languages"),
                InlineKeyboardButton("Set Default/Forced", callback_data="set_default_forced")
            ],
            [
                InlineKeyboardButton("Apply Changes", callback_data="apply_metadata_changes"),
                InlineKeyboardButton("Cancel", callback_data="cancel_operation")
            ]
        ]
        
        await callback_query.message.edit_text(
            "Select metadata to edit:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    async def show_added_files(self, callback_query: CallbackQuery):
        """Show list of added files"""
        user_id = callback_query.from_user.id
        session = user_sessions[user_id]
        
        files_info = []
        for i, file in enumerate(session['files'], 1):
            lang_info = f" (Language: {file['language']})" if file['language'] else ""
            files_info.append(f"{i}. {file['file_name']}{lang_info}")
        
        await callback_query.message.edit_text(
            "📁 Added files:\n\n" + "\n".join(files_info),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="back_to_actions")]
            ])
        )
    
    async def remove_last_file(self, callback_query: CallbackQuery):
        """Remove the last added file"""
        user_id = callback_query.from_user.id
        session = user_sessions[user_id]
        
        if not session['files']:
            await callback_query.answer("No files to remove.")
            return
        
        removed_file = session['files'].pop()
        await callback_query.answer(f"Removed: {removed_file['file_name']}")
        
        if not session['files']:
            del user_sessions[user_id]
            await callback_query.message.edit_text(
                "All files removed. Send a file to start again."
            )
        else:
            await self.show_action_buttons(callback_query.message, user_id)
    
    # Utility methods
    def detect_language(self, filename: str) -> Optional[str]:
        """Detect language from filename"""
        filename = filename.lower()
        parts = Path(filename).stem.split('.')
        
        for lang_code, variants in LANGUAGE_CODES.items():
            for variant in variants:
                if variant in parts:
                    return lang_code
        
        return None
    
    async def download_file(self, message: Message) -> str:
        """Download file with progress tracking"""
        user_id = message.from_user.id
        file_name = message.document.file_name if message.document else (
            message.video.file_name if message.video else (
                message.audio.file_name if message.audio else None
            )
        )
        
        if not file_name:
            raise ValueError("Could not determine file name")
        
        download_path = f"downloads/{user_id}/{file_name}"
        os.makedirs(os.path.dirname(download_path), exist_ok=True)
        
        # Create progress message
        progress_msg = await message.reply_text(
            f"📥 Downloading {file_name}...\n"
            "Progress: 0%\n"
            "Speed: 0 MB/s"
        )
        
        # Download with progress tracking
        start_time = asyncio.get_event_loop().time()
        last_update = 0
        downloaded = 0
        
        def progress(current, total):
            nonlocal last_update, downloaded
            downloaded = current
            
            now = asyncio.get_event_loop().time()
            if now - last_update >= 1:  # Update every second
                speed = (current / (now - start_time)) / 1024 / 1024  # MB/s
                percent = (current / total) * 100
                
                asyncio.create_task(progress_msg.edit_text(
                    f"📥 Downloading {file_name}...\n"
                    f"Progress: {percent:.1f}%\n"
                    f"Speed: {speed:.1f} MB/s\n"
                    f"Size: {current / 1024 / 1024:.1f} MB / {total / 1024 / 1024:.1f} MB"
                ))
                last_update = now
        
        if message.document:
            file = await message.download(
                file_name=download_path,
                progress=progress
            )
        elif message.video:
            file = await message.video.download(
                file_name=download_path,
                progress=progress
            )
        elif message.audio:
            file = await message.audio.download(
                file_name=download_path,
                progress=progress
            )
        else:
            raise ValueError("Unsupported message type")
        
        # Final progress update
        total_size = os.path.getsize(file)
        duration = asyncio.get_event_loop().time() - start_time
        speed = (total_size / duration) / 1024 / 1024  # MB/s
        
        await progress_msg.edit_text(
            f"✅ Download complete: {file_name}\n"
            f"Size: {total_size / 1024 / 1024:.1f} MB\n"
            f"Average speed: {speed:.1f} MB/s"
        )
        
        return file
    
    async def get_mkv_tracks(self, file_path: str) -> List[Dict]:
        """Get tracks information from MKV file using mkvinfo"""
        proc = await asyncio.create_subprocess_exec(
            'mkvinfo', file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"mkvinfo failed: {stderr.decode()}")
        
        # Parse mkvinfo output (simplified)
        tracks = []
        current_track = None
        lines = stdout.decode().splitlines()
        
        for line in lines:
            line = line.strip()
            if line.startswith("+ A track"):
                if current_track:
                    tracks.append(current_track)
                current_track = {'id': len(tracks) + 1}
            elif current_track:
                if "Track type:" in line:
                    current_track['type'] = line.split(":")[1].strip().lower()
                elif "Codec ID:" in line:
                    current_track['codec'] = line.split(":")[1].strip()
                elif "Language:" in line:
                    current_track['language'] = line.split(":")[1].strip()
        
        if current_track:
            tracks.append(current_track)
        
        return tracks
    
    async def extract_tracks(self, file_path: str, track_ids: List[int], output_dir: str) -> List[str]:
        """Extract tracks from MKV file"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Build mkvextract command
        command = ['mkvextract', file_path, 'tracks']
        for track_id in track_ids:
            output_file = os.path.join(output_dir, f"track_{track_id}")
            command.extend([f"{track_id}:{output_file}"])
        
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"mkvextract failed: {stderr.decode()}")
        
        # Get list of extracted files
        extracted_files = []
        for track_id in track_ids:
            # Check for common extensions
            for ext in ['.mkv', '.mp4', '.aac', '.srt', '.ass']:
                if os.path.exists(os.path.join(output_dir, f"track_{track_id}{ext}")):
                    extracted_files.append(os.path.join(output_dir, f"track_{track_id}{ext}"))
                    break
        
        return extracted_files
    
    async def mux_files(self, files: List[str], output_file: str, options: Dict) -> str:
        """Mux multiple files into one MKV"""
        # Build mkvmerge command
        command = ['mkvmerge', '-o', output_file]
        
        # Add files with options
        for file in files:
            command.append(file)
        
        # Add title if specified
        if options.get('title'):
            command.extend(['--title', options['title']])
        
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"mkvmerge failed: {stderr.decode()}")
        
        return output_file

if __name__ == "__main__":
    bot = MKVToolNixBot()
    bot.run()
