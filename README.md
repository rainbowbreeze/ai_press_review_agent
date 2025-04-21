# YouTube Video Monitor

A service that monitors multiple YouTube channels for new videos and sends detailed summaries to a Telegram chat using Gemini AI.

## Setup

1. Create a `.env` file with the following variables:
```
YOUTUBE_API_KEY=your_youtube_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
YOUTUBE_CHANNEL_IDS=channel_id1,channel_id2,channel_id3
GEMINI_API_KEY=your_gemini_api_key
```

2. Get your YouTube API key:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the YouTube Data API v3
   - Create credentials (API key)

3. Get your Gemini API key:
   - Go to the [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create an API key
   - Copy the key to your .env file

4. Set up your Telegram bot:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Create a new bot using `/newbot`
   - Save the bot token
   - Start a chat with your bot
   - Get your chat ID by sending a message to [@userinfobot](https://t.me/userinfobot)

5. Get YouTube Channel IDs:
   There are several ways to find a YouTube channel ID:

   a. From the channel URL:
      - If the URL looks like: `youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxxxxx`
        - The channel ID is everything after `/channel/`
      - If the URL looks like: `youtube.com/c/ChannelName` or `youtube.com/@username`
        - Go to the channel's home page
        - Right-click and select "View page source"
        - Search for "channelId" in the source code
        - The ID will be in the format "UCxxxxxxxxxxxxxxxxxxxxxxxxx"

   b. Using the YouTube Data API:
      ```python
      from googleapiclient.discovery import build
      
      youtube = build('youtube', 'v3', developerKey='YOUR_API_KEY')
      
      # For a custom URL (e.g., youtube.com/c/ChannelName)
      request = youtube.search().list(
          part="snippet",
          q="ChannelName",
          type="channel",
          maxResults=1
      )
      response = request.execute()
      channel_id = response['items'][0]['id']['channelId']
      
      # For a username (e.g., youtube.com/@username)
      request = youtube.channels().list(
          part="id",
          forUsername="username"
      )
      response = request.execute()
      channel_id = response['items'][0]['id']
      ```

   c. Using a Channel ID Finder tool:
      - Visit [Comment Picker's Channel ID Finder](https://commentpicker.com/youtube-channel-id.php)
      - Enter the channel URL or username
      - The tool will display the channel ID

   d. From the YouTube API response:
      - When you make any API call that returns channel information
      - The channel ID will be in the response under `items[0].id`

   Once you have the channel IDs, add them to your `.env` file, separated by commas:
   ```
   YOUTUBE_CHANNEL_IDS=UCxxxxxxxxxxxxxxxxxxxxxxxxx,UCyyyyyyyyyyyyyyyyyyyyyyyyy
   ```

## Deployment to Google Cloud Run

1. Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)

2. Build and deploy the container:
```bash
gcloud builds submit --tag gcr.io/[PROJECT-ID]/youtube-monitor
gcloud run deploy youtube-monitor \
  --image gcr.io/[PROJECT-ID]/youtube-monitor \
  --platform managed \
  --region [REGION] \
  --allow-unauthenticated
```

3. Set up Cloud Scheduler to run the service every 6 hours:
```bash
gcloud scheduler jobs create http youtube-monitor-job \
  --schedule "0 */6 * * *" \
  --uri "https://[REGION]-[PROJECT-ID].cloudfunctions.net/youtube-monitor" \
  --http-method GET
```

## Environment Variables

- `YOUTUBE_API_KEY`: Your YouTube Data API v3 key
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHAT_ID`: The chat ID where notifications will be sent
- `YOUTUBE_CHANNEL_IDS`: Comma-separated list of YouTube channel IDs to monitor
- `GEMINI_API_KEY`: Your Google Gemini API key

## Features

- Monitors multiple YouTube channels for new videos
- Checks for new videos every 6 hours
- Uses Gemini AI to generate detailed summaries including:
  - Comprehensive summary of main topics
  - Key takeaways
  - Notable quotes
  - Content analysis
- Sends formatted notifications to Telegram
- Includes fallback mechanism if Gemini API fails 