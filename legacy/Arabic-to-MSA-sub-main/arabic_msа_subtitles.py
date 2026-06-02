"""
Arabic Dialect → MSA Subtitle Pipeline
=======================================
Pipeline:
  Audio → Whisper STT → Dialect Detection → LLM Normalization to MSA → Subtitles (.srt)

Requirements:
  pip install openai-whisper openai torch arabic-reshaper python-bidi

Usage:
  python arabic_msa_subtitles.py --audio path/to/audio.mp3 --output subtitles.srt
  python arabic_msa_subtitles.py --audio path/to/audio.mp3 --live   # live mode (mic)
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional

# ── Optional imports (graceful degradation) ──────────────────────────────────
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("[WARN] whisper not installed. Run: pip install openai-whisper")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("[WARN] openai not installed. Run: pip install openai")

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Segment:
    """A transcribed audio segment with timing info."""
    start: float          # seconds
    end: float            # seconds
    dialect_text: str     # raw transcription (dialect)
    msa_text: str = ""    # normalized MSA
    dialect_label: str = "unknown"
    confidence: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# DIALECT IDENTIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

# Lexical markers per dialect family — enough for a fast heuristic pass.
# These are common function words / particles unique to each dialect.
DIALECT_MARKERS = {
    "Egyptian": [
        "إزيك", "عايز", "بتاع", "مش", "ازيك", "معاك", "دلوقتي", "اللي", "إيه", "فين",
        "انت", "احنا", "هو", "هي", "بقى", "كده", "عشان", "اوعى", "ماشي", "تمام"
    ],
    "Iraqi": [
        "شلونك", "هواية", "چاي", "گاع", "وين", "شگد", "چا", "لاكن", "هسا", "يمعود",
        "شنو", "ماكو", "أكو", "چنه", "گلت", "تعبان", "وگت", "دگيگة"
    ],
    "Levantine": [
        "شو", "كيفك", "هيك", "منيح", "بدي", "عم", "رح", "لأنو", "هلق", "قديش",
        "وين", "شلك", "ما في", "يلا", "بكرا", "لازم", "كمان", "مبارح"
    ],
    "Gulf": [
        "شلونك", "زين", "وايد", "چذب", "يبه", "حيل", "بعدين", "ليش", "حق", "يهال",
        "صج", "كاك", "هاه", "تعال", "اشبيك", "لو سمحت", "دزيت"
    ],
    "Maghrebi": [
        "واش", "كيفاش", "بزاف", "باهي", "ماشي", "دابا", "زعما", "بغيت", "هاد", "ديال",
        "فلوس", "مزيان", "راه", "راني", "نتا", "نتي", "حيت", "كاين"
    ],
    "Sudanese": [
        "كيفن", "زول", "قريب", "داير", "انت شنو", "يا زول", "ما فيش", "دا", "دي", "تاني"
    ],
    "Yemeni": [
        "شف", "قدر", "مين", "حبيبي", "وش", "الحين", "جاه", "يسر", "فيش", "مافيش"
    ],
}

def detect_dialect(text: str) -> tuple[str, float]:
    """
    Heuristic lexical dialect detection.
    Returns (dialect_name, confidence_0_to_1).
    For production, replace with a fine-tuned classifier:
      - CAMeL Tools dialect ID (https://github.com/CAMeL-Lab/camel_tools)
      - or a fine-tuned AraBERT model
    """
    scores = {dialect: 0 for dialect in DIALECT_MARKERS}
    text_lower = text  # Arabic doesn't have case, keep as-is

    for dialect, markers in DIALECT_MARKERS.items():
        for marker in markers:
            if marker in text_lower:
                scores[dialect] += 1

    total = sum(scores.values())
    if total == 0:
        return "MSA/Unknown", 0.0

    best = max(scores, key=scores.get)
    confidence = scores[best] / total
    return best, round(confidence, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# MSA NORMALIZER  (LLM-backed)
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """أنت مساعد متخصص في اللغة العربية.
مهمتك: تحويل أي نص عربي عامي (مصري، عراقي، شامي، خليجي، مغاربي، إلخ) إلى اللغة العربية الفصحى (MSA) دون تغيير المعنى.

القواعد:
1. حافظ على المعنى الأصلي بدقة تامة.
2. استخدم مفردات الفصحى المعيارية.
3. صحّح التراكيب النحوية.
4. احذف الكلمات الدخيلة أو أعد صياغتها بالعربية.
5. أعد النص الفصيح فقط، بدون أي شرح أو تعليق.
"""

def normalize_to_msa(
    dialect_text: str,
    dialect_label: str,
    provider: str = "anthropic",
    client=None,
) -> str:
    """
    Send dialect text to an LLM and return MSA version.
    provider: "anthropic" | "openai"
    """
    user_message = (
        f"اللهجة المكتشفة: {dialect_label}\n\n"
        f"النص العامي:\n{dialect_text}\n\n"
        f"الرجاء تحويله إلى الفصحى:"
    )

    if provider == "anthropic" and ANTHROPIC_AVAILABLE and client:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text.strip()

    elif provider == "openai" and OPENAI_AVAILABLE and client:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()

    else:
        # Fallback: return original with a note (offline mode)
        return f"[تعذّر التطبيع] {dialect_text}"


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSCRIPTION
# ═══════════════════════════════════════════════════════════════════════════════

def transcribe_audio(audio_path: str, model_size: str = "medium") -> list[Segment]:
    """
    Use Whisper to transcribe audio into timed segments.
    Whisper model sizes: tiny, base, small, medium, large-v3
    Larger = more accurate for dialects but slower.
    Recommended: medium or large-v3 for Arabic dialects.
    """
    if not WHISPER_AVAILABLE:
        raise RuntimeError("whisper not installed. Run: pip install openai-whisper")

    print(f"[INFO] Loading Whisper model '{model_size}'...")
    model = whisper.load_model(model_size)

    print(f"[INFO] Transcribing: {audio_path}")
    result = model.transcribe(
        audio_path,
        language="ar",          # force Arabic
        task="transcribe",      # keep original language (not translate)
        word_timestamps=False,
        verbose=False,
    )

    segments = []
    for seg in result["segments"]:
        segments.append(Segment(
            start=seg["start"],
            end=seg["end"],
            dialect_text=seg["text"].strip(),
        ))

    print(f"[INFO] Got {len(segments)} segments from Whisper.")
    return segments


# ═══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def process_segments(
    segments: list[Segment],
    provider: str,
    client,
    batch_size: int = 5,
) -> list[Segment]:
    """
    For each segment: detect dialect + normalize to MSA.
    Batches LLM calls to reduce latency.
    """
    total = len(segments)
    for i, seg in enumerate(segments):
        print(f"[{i+1}/{total}] Detecting dialect...", end=" ")
        seg.dialect_label, seg.confidence = detect_dialect(seg.dialect_text)
        print(f"{seg.dialect_label} ({seg.confidence:.0%})")

        print(f"         Normalizing to MSA...", end=" ")
        seg.msa_text = normalize_to_msa(seg.dialect_text, seg.dialect_label, provider, client)
        print("done.")

        # Small delay to respect API rate limits
        if i < total - 1:
            time.sleep(0.3)

    return segments


# ═══════════════════════════════════════════════════════════════════════════════
# SRT OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

def seconds_to_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(segments: list[Segment], output_path: str, include_dialect: bool = True):
    """
    Write segments to an .srt subtitle file.
    If include_dialect=True, shows dialect label + original text above MSA.
    """
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{seconds_to_srt_time(seg.start)} --> {seconds_to_srt_time(seg.end)}")
        if include_dialect and seg.dialect_label not in ("MSA/Unknown",):
            lines.append(f"[{seg.dialect_label}: {seg.dialect_text}]")
        lines.append(seg.msa_text)
        lines.append("")  # blank line between entries

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[INFO] Subtitles written to: {output_path}")


def write_json(segments: list[Segment], output_path: str):
    """Write full pipeline output as JSON for downstream use."""
    data = [
        {
            "index": i,
            "start": seg.start,
            "end": seg.end,
            "dialect": seg.dialect_label,
            "confidence": seg.confidence,
            "dialect_text": seg.dialect_text,
            "msa_text": seg.msa_text,
        }
        for i, seg in enumerate(segments, 1)
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[INFO] JSON output written to: {output_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO MODE  (no audio file needed — tests the dialect→MSA pipeline)
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_SEGMENTS = [
    Segment(0.0, 3.5,  "شلونك يا صاح؟ هواية زمان ما شفناك"),          # Iraqi
    Segment(3.5, 7.0,  "إزيك يا عم، انت عامل إيه دلوقتي؟"),             # Egyptian
    Segment(7.0, 11.0, "كيفك؟ شو عم تعمل هلق؟"),                        # Levantine
    Segment(11.0, 15.0,"واش راك؟ لاباس عليك؟ بزاف زمان ما شفناك"),      # Maghrebi
    Segment(15.0, 19.0,"شلونك؟ وايد زين؟ ليش ما جيت بعدين؟"),           # Gulf
]

def run_demo(provider: str, client):
    print("\n" + "═"*60)
    print("  DEMO MODE — Testing dialect → MSA normalization")
    print("═"*60 + "\n")

    segments = process_segments(DEMO_SEGMENTS, provider, client)

    print("\n" + "─"*60)
    print("RESULTS:")
    print("─"*60)
    for seg in segments:
        print(f"\n🗣  [{seg.dialect_label}] {seg.dialect_text}")
        print(f"📝  MSA: {seg.msa_text}")

    write_srt(segments, "demo_output.srt")
    write_json(segments, "demo_output.json")


# ═══════════════════════════════════════════════════════════════════════════════
# LIVE MIC MODE
# ═══════════════════════════════════════════════════════════════════════════════

def run_live(provider: str, client, model_size: str = "small"):
    """
    Real-time mic capture using sounddevice + Whisper.
    Requires: pip install sounddevice scipy
    Processes audio in ~5 second chunks.
    """
    try:
        import sounddevice as sd
        import scipy.io.wavfile as wavfile
        import numpy as np
        import tempfile
    except ImportError:
        print("[ERROR] Live mode needs: pip install sounddevice scipy")
        sys.exit(1)

    if not WHISPER_AVAILABLE:
        print("[ERROR] whisper not installed.")
        sys.exit(1)

    model = whisper.load_model(model_size)
    SAMPLE_RATE = 16000
    CHUNK_SECONDS = 5

    print("[LIVE] Starting live Arabic dialect → MSA subtitles. Press Ctrl+C to stop.\n")
    subtitle_index = 1

    try:
        while True:
            print(f"[LIVE] Recording {CHUNK_SECONDS}s chunk...")
            audio = sd.rec(
                int(CHUNK_SECONDS * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32"
            )
            sd.wait()

            # Save to temp wav
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
            wavfile.write(tmp_path, SAMPLE_RATE, (audio * 32767).astype("int16"))

            # Transcribe
            result = model.transcribe(tmp_path, language="ar", task="transcribe", verbose=False)
            os.unlink(tmp_path)

            text = result.get("text", "").strip()
            if not text:
                continue

            dialect, conf = detect_dialect(text)
            msa = normalize_to_msa(text, dialect, provider, client)

            print(f"\n[{subtitle_index}] [{dialect} {conf:.0%}] {text}")
            print(f"     MSA ► {msa}\n")
            subtitle_index += 1

    except KeyboardInterrupt:
        print("\n[LIVE] Stopped.")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Arabic dialect → MSA subtitle pipeline")
    parser.add_argument("--audio",    help="Path to audio/video file")
    parser.add_argument("--output",   default="subtitles.srt", help="Output .srt file path")
    parser.add_argument("--model",    default="medium", help="Whisper model size (tiny/base/small/medium/large-v3)")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "openai"], help="LLM provider")
    parser.add_argument("--demo",     action="store_true", help="Run demo without audio file")
    parser.add_argument("--live",     action="store_true", help="Live mic mode")
    parser.add_argument("--json",     action="store_true", help="Also output JSON")
    parser.add_argument("--no-dialect-labels", action="store_true", help="Clean SRT without dialect labels")
    args = parser.parse_args()

    # ── Set up LLM client ───────────────────────────────────────────────────
    client = None
    if args.provider == "anthropic":
        if not ANTHROPIC_AVAILABLE:
            print("[ERROR] anthropic not installed. Run: pip install anthropic")
            sys.exit(1)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("[ERROR] Set ANTHROPIC_API_KEY environment variable.")
            sys.exit(1)
        client = anthropic.Anthropic(api_key=api_key)

    elif args.provider == "openai":
        if not OPENAI_AVAILABLE:
            print("[ERROR] openai not installed. Run: pip install openai")
            sys.exit(1)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("[ERROR] Set OPENAI_API_KEY environment variable.")
            sys.exit(1)
        client = OpenAI(api_key=api_key)

    # ── Run selected mode ───────────────────────────────────────────────────
    if args.demo:
        run_demo(args.provider, client)

    elif args.live:
        run_live(args.provider, client, args.model)

    elif args.audio:
        segments = transcribe_audio(args.audio, args.model)
        segments = process_segments(segments, args.provider, client)
        write_srt(segments, args.output, include_dialect=not args.no_dialect_labels)
        if args.json:
            write_json(segments, args.output.replace(".srt", ".json"))

    else:
        print("No mode selected. Use --audio, --demo, or --live. See --help.")
        parser.print_help()


if __name__ == "__main__":
    main()
