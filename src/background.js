// background.js
// Handles: tabCapture, audio chunking, Whisper STT, Claude MSA normalization
// All API calls live here to keep keys out of content scripts.

const CHUNK_MS = 4000;       // 4s audio chunks — sweet spot for 1-3s latency
const SAMPLE_RATE = 16000;   // Whisper expects 16kHz mono

let captureState = {
  active: false,
  tabId: null,
  mediaRecorder: null,
  stream: null,
  audioCtx: null,
};

// ── Message router ────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  switch (msg.type) {
    case "START_CAPTURE":
      startCapture(msg.tabId).then(sendResponse);
      return true;

    case "STOP_CAPTURE":
      stopCapture();
      sendResponse({ ok: true });
      break;

    case "GET_STATE":
      sendResponse({ active: captureState.active });
      break;
  }
});

// ── Tab capture ───────────────────────────────────────────────────────────────

async function startCapture(tabId) {
  if (captureState.active) stopCapture();

  try {
    const stream = await new Promise((resolve, reject) => {
      chrome.tabCapture.capture({ audio: true, video: false }, (s) => {
        if (chrome.runtime.lastError || !s) reject(chrome.runtime.lastError);
        else resolve(s);
      });
    });

    captureState.stream  = stream;
    captureState.tabId   = tabId;
    captureState.active  = true;
    captureState.audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });

    // Route audio: capture → speakers (so user still hears video) + recorder
    const source = captureState.audioCtx.createMediaStreamSource(stream);
    const dest   = captureState.audioCtx.createMediaStreamDestination();
    source.connect(dest);
    source.connect(captureState.audioCtx.destination); // passthrough to speakers

    startChunkedRecording(dest.stream, tabId);
    return { ok: true };

  } catch (err) {
    captureState.active = false;
    return { ok: false, error: err.message };
  }
}

function stopCapture() {
  if (captureState.mediaRecorder?.state !== "inactive") {
    captureState.mediaRecorder?.stop();
  }
  captureState.stream?.getTracks().forEach(t => t.stop());
  captureState.audioCtx?.close();
  captureState = { active: false, tabId: null, mediaRecorder: null, stream: null, audioCtx: null };
}

// ── Chunked recording ─────────────────────────────────────────────────────────

function startChunkedRecording(stream, tabId) {
  const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
  captureState.mediaRecorder = recorder;

  recorder.ondataavailable = async (e) => {
    if (e.data.size < 500) return; // skip near-silent chunks
    try {
      const result = await transcribeAndNormalize(e.data);
      if (result?.msa) {
        chrome.tabs.sendMessage(tabId, { type: "SUBTITLE", text: result.msa });
      }
    } catch (err) {
      console.error("[MSA] Pipeline error:", err);
    }
  };

  recorder.start(CHUNK_MS);
}

// ── Whisper STT ───────────────────────────────────────────────────────────────

async function transcribeChunk(audioBlob) {
  const { openaiKey } = await chrome.storage.sync.get("openaiKey");
  if (!openaiKey) throw new Error("OpenAI API key not set.");

  const form = new FormData();
  form.append("file", audioBlob, "chunk.webm");
  form.append("model", "whisper-1");
  form.append("language", "ar");
  form.append("response_format", "text");

  const res = await fetch("https://api.openai.com/v1/audio/transcriptions", {
    method: "POST",
    headers: { Authorization: `Bearer ${openaiKey}` },
    body: form,
  });

  if (!res.ok) throw new Error(`Whisper error ${res.status}: ${await res.text()}`);
  const text = (await res.text()).trim();
  return text;
}

// ── Claude MSA normalization ───────────────────────────────────────────────────

const MSA_SYSTEM = `أنت متخصص في اللغة العربية. حوّل النص العامي التالي إلى اللغة العربية الفصحى المعيارية مع الحفاظ التام على المعنى. أعد النص الفصيح فقط، بدون أي شرح.`;

async function normalizeToMSA(dialectText) {
  const { anthropicKey } = await chrome.storage.sync.get("anthropicKey");
  if (!anthropicKey) throw new Error("Anthropic API key not set.");

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type":      "application/json",
      "x-api-key":         anthropicKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model:      "claude-haiku-4-5-20251001", // Haiku for speed, Sonnet if accuracy suffers
      max_tokens: 300,
      system:     MSA_SYSTEM,
      messages:   [{ role: "user", content: dialectText }],
    }),
  });

  if (!res.ok) throw new Error(`Claude error ${res.status}: ${await res.text()}`);
  const data = await res.json();
  return data.content[0].text.trim();
}

// ── Combined pipeline ─────────────────────────────────────────────────────────

async function transcribeAndNormalize(audioBlob) {
  const dialectText = await transcribeChunk(audioBlob);
  if (!dialectText || dialectText.length < 3) return null;

  // Skip normalization if Whisper already returned clean MSA
  // (happens when speaker is already using MSA)
  const msa = await normalizeToMSA(dialectText);
  return { dialect: dialectText, msa };
}
