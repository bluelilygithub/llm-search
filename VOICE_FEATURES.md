# Voice Features

## Text-to-Speech for AI Responses

### What's New
Added the ability to **listen to AI responses** using text-to-speech.

### Features
- 🔊 **Speaker button** appears next to every AI response
- 🎤 Uses **Web Speech API** (built into modern browsers)
- ⏸️ **Click to start/stop** speaking
- 🎨 **Visual feedback** - button changes to stop icon while speaking
- 🔄 **Auto-stop** - clicking another message stops the current one

### How to Use

#### As a User:
1. Ask your question (type or use mic)
2. Wait for AI response
3. Click the **speaker icon** (🔊) next to the timestamp
4. Listen to the response
5. Click again to stop

#### Voice Input (Already Existed):
- Click the **microphone** button in the input area
- Speak your question
- Text appears in the input field automatically

### Technical Details

**Frontend (JavaScript):**
- `speakMessage(button, messageId)` - Main TTS function
- `stopSpeech()` - Stops all speech
- Uses `SpeechSynthesisUtterance` for text-to-speech
- Stores message text in `data-messageText` attribute

**Styling (CSS):**
- `.speaker-btn` - Speaker button styling
- `.speaker-btn.speaking` - Active/speaking state with pulse animation
- `.message-time` - Container for timestamp and speaker button

### Browser Support
- ✅ Chrome/Edge (best support)
- ✅ Safari
- ✅ Firefox
- ❌ IE (not supported)

### Settings
Current defaults (can be customized in code):
- **Rate:** 1.0 (normal speed)
- **Pitch:** 1.0 (normal pitch)
- **Volume:** 1.0 (full volume)

### Future Enhancements (Optional)
- Voice selection (male/female, accents)
- Speed control
- Pause/resume functionality
- Download as audio file

