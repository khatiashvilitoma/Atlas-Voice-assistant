# Atlas Voice Assistant

A private AI voice assistant for Windows that runs on your own PC. Talk or type to Atlas, and it answers out loud.

- **Local AI** through [Ollama](https://ollama.com). Your conversations stay on your PC.
- **Speech-to-text** with [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
- **Natural voice** with [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), with the Windows voice as a backup.
- **Memory** between sessions, plus personal facts from `about_me.txt`.
- **Knows the date and time.**
- **Tools** that the AI decides to use on its own:
  - Look at your screen ("What's this error on my screen?")
  - Open apps and websites ("Open VS Code", "Open YouTube")
  - Reminders ("Remind me in 20 minutes to stretch")
  - PC info ("How much RAM am I using?")
  - Web search and weather (these two need the internet)
- **Two ways to use it:** a chat window (`atlas_app.py`) or the terminal (`voice_assistant.py`).

## Requirements

- Windows 10 or 11
- Python 3.12
- [Ollama](https://ollama.com/download)
- A microphone and speakers
- An Ollama model that supports tools and images. Atlas was tested with `bonsai-2:27b` (smart, but slow and very heavy on an 8 GB graphics card). `qwen3:8b` is a lighter, faster choice for chatting; it supports tools, but not images, so "look at my screen" won't work with it.

## Setup

1. **Install Ollama** and download the model set in `OLLAMA_MODEL` (default `bonsai-2:27b`):
   ```powershell
   ollama pull bonsai-2:27b
   ```
   For a lighter, faster model, run `ollama pull qwen3:8b` instead and set `OLLAMA_MODEL = "qwen3:8b"`.

2. **Install the Python packages:**
   ```powershell
   python -m pip install -r requirements.txt
   ```

3. **Download the Kokoro voice files** (about 337 MB) into a folder named `kokoro` inside this project:
   - [kokoro-v1.0.onnx](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx)
   - [voices-v1.0.bin](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin)

   If the files are missing, Atlas uses the built-in Windows voice instead.

4. **Optional:** copy `about_me.example.txt` to `about_me.txt` and add facts about yourself.

## Run

Make sure the Ollama app is running, then start either the window app:
```powershell
python atlas_app.py
```
or the terminal version:
```powershell
python voice_assistant.py
```

- **Type** a message and press Enter.
- **Talk:** in the window app, click **Talk**, speak, then click **Stop & send**. In the terminal, press Enter, speak, then press Enter again.
- The first answer is slower while the model loads.

## Settings

Change these at the top of `voice_assistant.py`:

| Setting | What it does |
|---|---|
| `OLLAMA_MODEL` | Which Ollama model to use, e.g. `"qwen3:8b"` |
| `ASSISTANT_NAME` | The assistant's name |
| `KOKORO_VOICE` | The voice, e.g. `"am_michael"`, `"af_heart"`, `"bm_george"` |
| `KOKORO_SPEED` | Speaking speed (`1.0` = normal) |
| `WHISPER_MODEL` | Speech recognition model: `"tiny"`, `"base"` or `"small"` |
| `CONTEXT_SIZE` | How much text the AI can see at once |

To add apps that Atlas can open, edit the `APPS` list in `atlas_tools.py`.

## Privacy

- The AI, speech recognition and voice all run on your PC.
- Screenshots are sent only to your local model and are never saved.
- Only web search ([DuckDuckGo](https://duckduckgo.com)) and weather ([Open-Meteo](https://open-meteo.com)) contact the internet.
- Your conversations (`memory.json`) and personal facts (`about_me.txt`) are kept out of Git by `.gitignore`. Delete `memory.json` to make Atlas forget past conversations.

## Safety

Atlas can only open apps from the fixed `APPS` list and normal `http`/`https` websites. It never runs other commands, even if text on your screen or in search results tells it to.
