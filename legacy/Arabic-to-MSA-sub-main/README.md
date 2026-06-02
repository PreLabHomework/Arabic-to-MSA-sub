# Arabic MSA Subtitle Pipeline

A Python pipeline for converting Arabic dialect audio into Modern Standard Arabic subtitles.

The project takes an audio or video file, transcribes the Arabic speech with Whisper, optionally detects the dialect family using lexical markers, normalizes the dialect text into MSA using an LLM, and exports the result as an `.srt` subtitle file.

## Project status

Prototype.

The core pipeline is implemented, but the project is still being cleaned up and tested. Some features, especially live microphone mode and dialect detection accuracy, should be treated as experimental.

## What it does

- Accepts Arabic audio or video input
- Uses Whisper for speech-to-text transcription
- Preserves Arabic transcription instead of translating to English
- Detects common Arabic dialect families using heuristic lexical markers
- Converts dialect Arabic into MSA using Anthropic or OpenAI models
- Exports subtitles in `.srt` format
- Can optionally export full results as JSON
- Includes demo mode for testing without an audio file
- Includes experimental live microphone mode

## Supported dialect families

The current heuristic detector includes markers for:

- Egyptian
- Iraqi
- Levantine
- Gulf
- Maghrebi
- Sudanese
- Yemeni
- MSA or unknown

This is not a production-grade dialect classifier. It is a lightweight first pass that can be replaced later with a stronger Arabic dialect identification model.

## Tech stack

- Python
- Whisper
- OpenAI API
- Anthropic API
- SRT subtitle formatting
- Arabic NLP
- Heuristic dialect detection

## Files

| File | Description |
| --- | --- |
| `arabic_msa_subtitles.py` | Main pipeline with dialect detection, provider options, SRT and JSON output, demo mode, and live mode |
| `arabic_to_msa.py` | Simpler version focused on Whisper transcription and Anthropic-based MSA subtitle generation |

## Installation

```bash
pip install openai-whisper openai anthropic torch

For live microphone mode:

pip install sounddevice scipy
Usage

Run on an audio or video file:

python arabic_msa_subtitles.py --audio path/to/audio.mp3 --output subtitles.srt

Use a larger Whisper model for heavier accents:

python arabic_msa_subtitles.py --audio path/to/audio.mp3 --model large-v3

Run demo mode:

python arabic_msa_subtitles.py --demo

Run live microphone mode:

python arabic_msa_subtitles.py --live

Export JSON along with subtitles:

python arabic_msa_subtitles.py --audio path/to/audio.mp3 --output subtitles.srt --json

Generate clean subtitles without dialect labels:

python arabic_msa_subtitles.py --audio path/to/audio.mp3 --no-dialect-labels
API keys

For Anthropic:

set ANTHROPIC_API_KEY=your_key_here

For OpenAI:

set OPENAI_API_KEY=your_key_here

On macOS or Linux, use export instead of set.

My role

I built the pipeline structure, transcription workflow, dialect marker system, LLM normalization step, SRT generation logic, demo mode, and experimental live mode. The project was designed as a practical Arabic NLP tool for turning dialect speech into readable MSA subtitles.

Limitations
Dialect detection is heuristic, not a trained classifier
Output quality depends on Whisper transcription accuracy
Heavy dialects, noisy audio, and overlapping speakers may reduce quality
LLM normalization requires an API key
Live mode is experimental
The project does not currently include a GUI
Future improvements
Replace heuristic dialect detection with a trained Arabic dialect classifier
Add batch subtitle generation for folders of videos
Add speaker labels
Add subtitle timing cleanup
Add a simple desktop or web interface
Improve support for mixed dialect conversations
