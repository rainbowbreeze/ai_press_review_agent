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
from youtube_transcript_api.formatters import TextFormatter
import asyncio

# Load environment variables
load_dotenv()

# Configuration
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
CHANNEL_IDS = os.getenv('YOUTUBE_CHANNEL_IDS', '').split(',')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Initialize YouTube API client
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-lite')

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
        print(f"Error sending error notification: {str(e)}")

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
            print(f"No videos found for channel {channel_id}")
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
        print(error_message)
        await send_error_notification("N/A", f"Channel {channel_id}", error_message)
        return None

def get_video_transcription(video_id, video_title):
    """Extract the video transcription using youtube-transcript-api."""
    try:
        # Get the transcript
        transcript_list = YouTubeTranscriptApi().fetch(video_id)
        
        # Format the transcript into a single string
        formatter = TextFormatter()
        transcript_text = formatter.format_transcript(transcript_list)
        
        return transcript_text, None
    except Exception as e:
        error_message = f"Error getting video transcription: {str(e)}"
        print(error_message)
        return None, error_message

async def create_video_summary(video):
    """Create a detailed summary of the video using Gemini API."""
    video_url = f"https://www.youtube.com/watch?v={video['video_id']}"
    
    # Get video transcription
    transcription, error_message = get_video_transcription(video['video_id'], video['title'])
    
    if not transcription:
        print(f"No transcription available for video {video['title']}")
        # Send error notification
        await send_error_notification(video['video_id'], video['title'], error_message if error_message is not None else "No transcription available")
        return None
    
    prompt = f"""
    Please analyze this YouTube video and provide a concise summary. Here are the details:

    Video Title: {video['title']}
    Video Description: {video['description']}
    Video URL: {video_url}

    Full Transcript:
    {transcription}

    Based on the above information, please provide a structured summary that includes:

    1. DETAILED CONTENT BREAKDOWN
    - Break down the video content into logical sections
    - Explain the flow of the discussion
    - Note any important examples or demonstrations

    2. TECHNICAL DETAILS (if applicable)
    - Note any specific tools, technologies, or methods mentioned
    - Explain any technical concepts or processes
    - List any code snippets or commands if relevant

    Please keep the summary concise and focused on the most important points. Aim for a length that can be easily read in less than one minute.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating summary with Gemini: {str(e)}")
        # Send error notification for Gemini failure
        await send_error_notification(video['video_id'], video['title'], f"Error generating summary with Gemini: {str(e)}")
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
🎥 New Video Alert! 🎥

📺 Channel: {channel_name}
📺 Title: {video['title']}
📝 Summary: {summary}
🔗 Watch here: https://www.youtube.com/watch?v={video['video_id']}
        """
        
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TelegramError as e:
        print(f"Error sending Telegram message: {str(e)}")

async def check_and_notify():
    """Main function to check for new videos and send notifications."""
    for channel_id in CHANNEL_IDS:
        if not channel_id.strip():
            continue
            
        # Get the latest video
        latest_video = await get_latest_video(channel_id.strip())
        if not latest_video:
            continue
        
        # Check if the video was published in the last 6 hours
        video_published_at = datetime.fromisoformat(latest_video['published_at'].replace('Z', '+00:00'))
        if datetime.now(video_published_at.tzinfo) - video_published_at > timedelta(hours=6):
            print(f"No new videos in the last 6 hours for channel {channel_id}")
            continue
        
        # Create summary and send notification
        summary = await create_video_summary(latest_video)
        if summary:  # Only send notification if summary was generated
            await send_telegram_message(latest_video, summary)
            print(f"New video notification and summary sent successfully for channel {channel_id}")
        else:
            print(f"New video notification sent for channel {channel_id}, but there were errors in creating the summary")

@functions_framework.http
def perform_press_review(request):
    """Cloud Function entry point."""
    # Run the async function
    asyncio.run(check_and_notify())
    return "AI Press Review Agent completed successfully"
