"""
Arabic Dialect → MSA Subtitle Generator
========================================
Give it a video or audio file, get back an .srt subtitle file in MSA.

Install:
    pip install openai-whisper anthropic

Usage:
    python arabic_to_msa.py myvideo.mp4
    python arabic_to_msa.py myvideo.mp4 --output subs.srt
    python arabic_to_msa.py myvideo.mp4 --model large-v3   # better accuracy for heavy accents
"""

import argparse
import os
import sys
import time

# ── Dependency checks ─────────────────────────────────────────────────────────
try:
    import whisper
except ImportError:
    sys.exit("Missing dependency. Run:  pip install openai-whisper")

try:
    import anthropic
except ImportError:
    sys.exit("Missing dependency. Run:  pip install anthropic")


# ── Helpers ───────────────────────────────────────────────────────────────────

def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp: HH:MM:SS,mmm"""
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


# ── Core pipeline ─────────────────────────────────────────────────────────────

def transcribe(audio_path: str, model_size: str) -> list[dict]:
    """Step 1: Whisper transcribes the audio into dialect Arabic segments."""
    print(f"Loading Whisper ({model_size})...")
    model = whisper.load_model(model_size)

    print("Transcribing audio...")
    result = model.transcribe(
        audio_path,
        language="ar",       # force Arabic
        task="transcribe",   # keep original language, don't translate
        verbose=False,
    )

    segments = [
        {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
        for s in result["segments"]
        if s["text"].strip()
    ]
    print(f"Got {len(segments)} segments.\n")
    return segments


def to_msa(segments: list[dict], client: anthropic.Anthropic) -> list[dict]:
    """Step 2: Send each segment to Claude to normalize dialect → MSA."""
    system_prompt = (
        "أنت متخصص في اللغة العربية. "
        "حوّل النص العامي التالي إلى اللغة العربية الفصحى المعيارية (MSA) "
        "مع الحفاظ التام على المعنى الأصلي. "
        "أعد النص الفصيح فقط، بدون أي شرح أو تعليق."
    )

    total = len(segments)
    for i, seg in enumerate(segments):
        print(f"[{i+1}/{total}] Normalizing: {seg['text'][:60]}...")

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": seg["text"]}],
        )

        seg["msa"] = response.content[0].text.strip()
        print(f"          → {seg['msa'][:60]}")

        # Respect API rate limits
        if i < total - 1:
            time.sleep(0.25)

    return segments


def write_srt(segments: list[dict], output_path: str):
    """Step 3: Write the MSA text as a standard .srt subtitle file."""
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}")
        lines.append(seg["msa"])
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nSubtitles saved to: {output_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Arabic dialect audio → MSA subtitles")
    parser.add_argument("audio", help="Path to audio or video file")
    parser.add_argument("--output", help="Output .srt file (default: same name as input)")
    parser.add_argument(
        "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size. Use large-v3 for heavy accents (Maghrebi, Yemeni, etc.)"
    )
    args = parser.parse_args()

    # Default output path: same filename, .srt extension
    output_path = args.output or os.path.splitext(args.audio)[0] + ".srt"

    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Set your API key first:  export ANTHROPIC_API_KEY=sk-ant-...")

    client = anthropic.Anthropic(api_key=api_key)

    # Run the pipeline
    segments = transcribe(args.audio, args.model)
    segments = to_msa(segments, client)
    write_srt(segments, output_path)


if __name__ == "__main__":
    main()
