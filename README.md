# Arabic MSA Subtitles: Chrome Extension

Live Arabic dialect → MSA subtitle overlay for YouTube.

## Features

- Live audio capture from any YouTube video
- Whisper API (OpenAI) for dialect-aware transcription
- Claude Haiku for fast dialect → MSA normalization
- On-video overlay OR floating sidebar OR both — toggle in popup
- Font size and subtitle position (top/bottom) controls
- API keys stored securely in chrome.storage.sync

## Install (Developer Mode)

1. Open Chrome and go to `chrome://extensions`
2. Enable "Developer mode" (top right toggle)
3. Click "Load unpacked"
4. Select this folder (`arabic-msa-extension/`)

## Setup

1. Click the extension icon on any YouTube video page
2. Enter your API keys:
   - **OpenAI key** — for Whisper STT (`sk-...`)
   - **Anthropic key** — for Claude MSA normalization (`sk-ant-...`)
3. Click "حفظ المفاتيح" (Save Keys)
4. Toggle the main switch ON

## How It Works

```
YouTube tab audio
    │
    ▼
chrome.tabCapture API (background.js)
    │  4-second chunks (WebM/Opus)
    ▼
OpenAI Whisper API
    │  dialect Arabic text
    ▼
Anthropic Claude Haiku API
    │  MSA Arabic text
    ▼
content.js injects subtitle into page
    │
    ├── Overlay: renders on the video itself
    └── Sidebar: floating panel on the right
```

## File Structure

```
arabic-msa-extension/
├── manifest.json
├── icons/
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── src/
    ├── background.js   — audio capture + API calls
    ├── content.js      — subtitle DOM injection
    ├── subtitles.css   — overlay + sidebar styles
    ├── popup.html      — settings UI
    └── popup.js        — popup controls
```

## Icons

The `icons/` folder needs PNG files at 16x16, 48x48, and 128x128.
You can generate simple placeholder icons with any image editor,
or use a text-to-image tool to make an "MSA" branded icon.

## Latency

- Whisper API: ~0.5-1.5s for a 4s chunk
- Claude Haiku: ~0.3-0.7s
- Total expected: 1-3s end to end

For better dialect accuracy on heavy accents (Maghrebi, Yemeni),
switch to `claude-sonnet-4-6` in background.js — slightly slower but
noticeably more accurate on tricky dialects.

## Cost Estimate

At moderate YouTube usage (~30 min/day):
- Whisper: ~$0.006/min → ~$0.18/day
- Claude Haiku: ~$0.001/request × ~450 chunks → ~$0.45/day
- Total: roughly $0.60/day of active use
