import functions_framework
import os
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
from youtube_transcript_api.formatters import TextFormatter
import asyncio
import logging
import sys

# Configure logging
def setup_logging():
    """Configure console logging."""
    # Create logger
    logger = logging.getLogger('ai_press_review')
    logger.setLevel(logging.INFO)

    # Create console formatter
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)

    # Add handler to logger
    logger.addHandler(console_handler)

    return logger

# Initialize logger
logger = setup_logging()

# Load environment variables
load_dotenv()

# Configuration
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
CHANNEL_IDS = os.getenv('YOUTUBE_CHANNEL_IDS', '').split(',')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
WEBSHARE_PROXY_USERNAME = os.getenv('WEBSHARE_PROXY_USERNAME')
WEBSHARE_PROXY_PASSWORD = os.getenv('WEBSHARE_PROXY_PASSWORD')

# Initialize YouTube API client
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-lite')

def is_cloud_function():
    """Check if the code is running in a Google Cloud Function environment."""
    return os.getenv('FUNCTION_TARGET') is not None

async def send_error_notification(video_id, video_title, error_message):
    """Send an error notification to Telegram."""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        message = f"""
⚠️ Video processing error alert! ⚠️

📺 Video: {video_title}
🔗 URL: https://www.youtube.com/watch?v={video_id}
❌ Error: {error_message}

The video won't be summarized because of the error.
        """
        
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TelegramError as e:
        logger.error(error_message)

async def get_latest_video(channel_id):
    """Fetch the latest video from the specified YouTube channel."""
    try:
        request = youtube.search().list(
            part="snippet",
            channelId=channel_id,
            maxResults=1,
            order="date",
            type="video"
        )
        response = request.execute()
        
        if not response['items']:
            logger.info(f"No videos found for channel {channel_id}")
            return None
        
        video = response['items'][0]
        return {
            'video_id': video['id']['videoId'],
            'title': video['snippet']['title'],
            'published_at': video['snippet']['publishedAt'],
            'description': video['snippet']['description'],
            'channel_id': channel_id
        }
    except Exception as e:
        error_message = f"Error getting latest video from channel {channel_id}: {str(e)}"
        logger.error(error_message)
        await send_error_notification("N/A", f"Channel {channel_id}", error_message)
        return None

def get_video_transcription_via_yt_transcription_lib(video_id, video_title):
    """Extract the video transcription using youtube-transcript-api.

    https://pypi.org/project/youtube-transcript-api/
    This is an python API which allows you to get the transcripts/subtitles for a given YouTube video.
      It also works for automatically generated subtitles, supports translating subtitles
      and it does not require a headless browser, like other selenium based solutions do!
    """
    try:

        if is_cloud_function():
            # all requests done by ytt_api will now be proxied through Webshare
            # https://github.com/jdepoix/youtube-transcript-api?tab=readme-ov-file#working-around-ip-bans-requestblocked-or-ipblocked-exception
            ytt_api = YouTubeTranscriptApi(
                proxy_config=WebshareProxyConfig(
                    proxy_username=WEBSHARE_PROXY_USERNAME,
                    proxy_password=WEBSHARE_PROXY_PASSWORD,
                )
            )
        else:
            # When running locally, we don't need to proxy through Webshare because
            # YouTube doesn't block "consumer" IP addresses.
            ytt_api = YouTubeTranscriptApi()

        # Get the transcript
        transcript_list = ytt_api.fetch(video_id)
        
        # Format the transcript into a single string
        formatter = TextFormatter()
        transcript_text = formatter.format_transcript(transcript_list)
        
        return transcript_text, None
        
    except Exception as e:
        error_message = f"Error getting video transcription: {str(e)}"
        logger.error(error_message)
        return None, error_message

def get_video_transcription_via_yt_api(video_id, video_title):
    """Extract the video transcription using YouTube Data API.

        This method doesn't really work, at least with this code
    """
    try:
        # Get the captions list
        captions_request = youtube.captions().list(
            part="snippet",
            videoId=video_id
        )
        captions_response = captions_request.execute()
        
        if not captions_response.get('items'):
            logger.warning(f"No captions available for video {video_id}")
            return None, "No captions available for this video"
        
        # Get the first available caption track (usually the main one)
        caption_id = captions_response['items'][0]['id']
        
        # Download the caption track
        caption_request = youtube.captions().download(
            id=caption_id
        )
        caption_response = caption_request.execute()
        
        # The response is in TTML format, we need to parse it
        # This is a simplified parsing, you might need to adjust based on the actual format
        transcript_text = ""
        for line in caption_response.split('\n'):
            if '<text' in line:
                # Extract the text content
                text = line.split('>')[1].split('<')[0]
                transcript_text += text + " "
        
        return transcript_text.strip(), None
        
    except Exception as e:
        error_message = f"Error getting video transcription: {str(e)}"
        logger.error(error_message)
        return None, error_message

async def create_video_summary(video):
    """Create a detailed summary of the video using Gemini API."""
    video_url = f"https://www.youtube.com/watch?v={video['video_id']}"
    
    # Get video transcription based on environment
    transcription, error_message = get_video_transcription_via_yt_transcription_lib(video['video_id'], video['title'])
    
    if not transcription:
        # Send error notification
        # logger.warning(f"No transcription available for video {video['title']}")
        await send_error_notification(video['video_id'], video['title'], error_message if error_message is not None else "No transcription available")
        return None
    
    prompt = f"""
    Please analyze this YouTube video and provide a concise summary.
    
    Here are the details:
    Video Title: {video['title']}
    Video Description: {video['description']}
    Video URL: {video_url}

    Full Transcript:
    {transcription}

    Based on the above information, please provide a structured summary that includes:

    *DETAILED CONTENT BREAKDOWN*
    - Break down the video content into logical sections
    - Explain the flow of the discussion
    - Note any important examples or demonstrations

    *TECHNICAL DETAILS* (if applicable)
    - Note any specific tools, technologies, or methods mentioned
    - Explain any technical concepts or processes
    - List any code snippets or commands if relevant

    Please format your response using Telegram markdown:
    - Use *asterisks* for bold text
    - Use _underscores_ for italic text
    - Use `backticks` for code snippets
    - Use - for bullet points
    - Keep the summary concise and focused on the most important points
    - Aim for a length that can be read in less than one minute
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        error_message = f"Error generating summary with Gemini: {str(e)}"
        logger.error(error_message)
        await send_error_notification(video['video_id'], video['title'], error_message)
        return None

async def send_telegram_message(video, summary):
    """Send a message to the specified Telegram chat."""
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        # Get channel information
        channel_request = youtube.channels().list(
            part="snippet",
            id=video['channel_id']
        )
        channel_response = channel_request.execute()
        channel_name = channel_response['items'][0]['snippet']['title'] if channel_response['items'] else "Unknown Channel"
        
        message = f"""
🎥 *New Video Alert!* 🎥

📺 Channel: {channel_name}
📺 Title: {video['title']}
📝 Summary:
{summary}
🔗 Watch here: https://www.youtube.com/watch?v={video['video_id']}
        """
        
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            disable_web_page_preview=False
        )
    except TelegramError as e:
        logger.error(f"Error sending Telegram message: {str(e)}")

async def check_and_notify():
    """Main function to check for new videos and send notifications."""
    for channel_id in CHANNEL_IDS:
        if not channel_id.strip():
            continue
            
        # Get the latest video
        latest_video = await get_latest_video(channel_id.strip())
        if not latest_video:
            logger.warning(f"No videos found for channel {channel_id}")
            continue
        
        # Check if the video was published in the last 6 hours
        video_published_at = datetime.fromisoformat(latest_video['published_at'].replace('Z', '+00:00'))
        if datetime.now(video_published_at.tzinfo) - video_published_at > timedelta(hours=6):
            logger.info(f"No new videos in the last 6 hours for channel {channel_id}")
            continue
        
        # Create summary and send notification
        summary = await create_video_summary(latest_video)
        if summary:  # Only send notification if summary was generated
            await send_telegram_message(latest_video, summary)
            logger.info(f"Successfully processed and notified about a new video from channel {channel_id}")
        else:
            logger.warning(f"Failed to process video from channel {channel_id}")

@functions_framework.http
def perform_press_review(request):
    """Cloud Function entry point."""
    # Run the async function
    asyncio.run(check_and_notify())
    return "AI Press Review Agent completed successfully"

def perform_press_review_via_cli():
    """Command line entry point."""
    logger.info("Starting AI Press Review Agent via CLI")
    asyncio.run(check_and_notify())
    logger.info("AI Press Review Agent completed successfully via CLI")

if __name__ == "__main__":
    perform_press_review_via_cli()
