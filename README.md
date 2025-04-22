# AI Press Review Agent

A service that monitors multiple YouTube channels for new videos and sends detailed summaries to a Telegram chat.

## Setup

1. Create a `.env.yaml` file with the following variables:
```yaml
YOUTUBE_API_KEY: "your_youtube_api_key"
TELEGRAM_BOT_TOKEN: "your_telegram_bot_token"
TELEGRAM_CHAT_ID: "your_telegram_chat_id"
YOUTUBE_CHANNEL_IDS: "channel_id1,channel_id2,channel_id3"
GEMINI_API_KEY: "your_gemini_api_key"
WEBSHARE_PROXY_USERNAME: "your_webshare_username"  # Optional: For YouTube API requests
WEBSHARE_PROXY_PASSWORD: "your_webshare_password"  # Optional: For YouTube API requests
```

2. Get your YouTube API key:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the YouTube Data API v3
   - Create credentials (API key)

3. Get your Gemini API key:
   - Go to the [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create an API key
   - Copy the key to your .env.yaml file

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

   Once you have the channel IDs, add them to your `.env.yaml` file, separated by commas:
   ```yaml
   YOUTUBE_CHANNEL_IDS: "UCxxxxxxxxxxxxxxxxxxxxxxxxx,UCyyyyyyyyyyyyyyyyyyyyyyyyy"
   ```

## Deployment to Google Cloud Functions

1. Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)

2. Authenticate with Google Cloud:
```bash
gcloud auth login
gcloud config set project [YOUR_PROJECT_ID]
```

3. Enable required APIs:
```bash
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

4. Deploy the function using Cloud Functions:
```bash
gcloud functions deploy ai_press_review_agent \
  --runtime python311 \
  --trigger-http \
  --entry-point perform_press_review \
  --region [YOUR_REGION] \
  --timeout 540s  \
  --memory 512MB \
  --source . \
  --allow-unauthenticated \
  --env-vars-file .env.yaml 
```

The function will be deployed with the following configuration:
- Runtime: Python 3.11
- Region: [YOUR_REGION] (for example, europe-west9)
- Memory: 512MB
- Timeout: 540 seconds
- Trigger: HTTP
- Entry point: perform_press_review

([source](https://cloud.google.com/sdk/gcloud/reference/functions/deploy))

5. Set up Cloud Scheduler to run the function periodically:
```bash
gcloud scheduler jobs create http ai-press-review-job \
  --schedule "0 */6 * * *" \
  --uri "https://[YOUR_REGION]-[YOUR_PROJECT_ID].cloudfunctions.net/ai_press_review_agent" \
  --http-method GET
```

### Updating the Schedule

To change how often the function runs:

1. Delete the existing scheduler job:
```bash
gcloud scheduler jobs delete ai-press-review-job
```

2. Create a new scheduler job with the desired schedule:
```bash
gcloud scheduler jobs create http ai-press-review-job \
  --schedule "[NEW_SCHEDULE]" \
  --uri "https://[YOUR_REGION]-[YOUR_PROJECT_ID].cloudfunctions.net/ai_press_review_agent" \
  --http-method GET
```

Common schedule formats:
- Every 6 hours: `"0 */6 * * *"`
- Every 12 hours: `"0 */12 * * *"`
- Daily at midnight: `"0 0 * * *"`
- Weekly on Monday at 9 AM: `"0 9 * * 1"`

## Environment Variables

- `YOUTUBE_API_KEY`: Your YouTube Data API v3 key
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHAT_ID`: The chat ID where notifications will be sent
- `YOUTUBE_CHANNEL_IDS`: Comma-separated list of YouTube channel IDs to monitor
- `GEMINI_API_KEY`: Your Google Gemini API key
- `WEBSHARE_PROXY_USERNAME`: Your WebShare Proxy username (optional)
- `WEBSHARE_PROXY_PASSWORD`: Your WebShare Proxy password (optional)

### Proxy Configuration (Optional)

If you're experiencing transcriptions error, this is because blocked IP of cloud providers. It's well documented [here](https://github.com/jdepoix/youtube-transcript-api?tab=readme-ov-file#working-around-ip-bans-requestblocked-or-ipblocked-exception)

#### Setting up WebShare Proxy

1. Sign up for a WebShare account at [webshare.io](https://www.webshare.io/)
2. Choose a proxy plan that suits your needs
3. Get your proxy credentials from the WebShare dashboard
4. Add the following to your `.env.yaml` file:

```yaml
WEBSHARE_PROXY_USERNAME: "your_webshare_username"
WEBSHARE_PROXY_PASSWORD: "your_webshare_password"
```

The proxy will be automatically configured for:
- Video transcript fetching

Note: The proxy is optional, and generally not necessary when running the agent locally

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