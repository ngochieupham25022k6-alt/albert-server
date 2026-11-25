# server.py - Server AI Realtime 24/7 cho A.L.B.E.R.T. (FastAPI + Gemini Flash + Memory + IoT Relay + Web Chat Console)
import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from agent import CONFIG, search_web, control_relay, speak_text, call_gemini
from memory_manager import load_memory, add_fact, delete_fact

app = FastAPI(title="A.L.B.E.R.T. AI Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections = []
AUDIO_OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "live_reply.mp3")
chat_history = []
SERVER_HOST = os.environ.get("SERVER_HOST", "localhost")
SERVER_PORT_NUM = int(os.environ.get("PORT", os.environ.get("SERVER_PORT", "8000")))

# ==============================================================================
# 1. GIAO DIEN WEB CONSOLE TRUC TIEP CHO NGUOI DUNG TEST (VOICE + TEXT + RELAY + MEMORY)
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>A.L.B.E.R.T. - AI Advisor Console</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0F0F11; color: #E5E5E7; display: flex; height: 100vh; overflow: hidden; }
            
            /* Sidebar dieu khien */
            .sidebar { width: 360px; background: #16161A; border-right: 1px solid #27272A; padding: 18px; display: flex; flex-direction: column; gap: 14px; overflow-y: auto; }
            .brand h2 { color: #FF9900; font-size: 20px; letter-spacing: 1px; display: flex; align-items: center; gap: 8px; }
            .brand p { font-size: 11px; color: #71717A; margin-top: 3px; }
            
            .card { background: #1F1F24; border: 1px solid #2E2E33; border-radius: 8px; padding: 14px; }
            .card h4 { font-size: 12px; text-transform: uppercase; color: #A1A1AA; margin-bottom: 10px; letter-spacing: 0.5px; display: flex; justify-content: space-between; align-items: center; }
            
            .relay-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
            .relay-row:last-child { margin-bottom: 0; }
            .relay-name { font-size: 13px; font-weight: 500; }
            .status-tag { font-size: 10px; padding: 2px 7px; border-radius: 4px; font-weight: bold; background: #27272A; color: #71717A; }
            .status-tag.active { background: #FF9900; color: #000; }

            /* Memory Card */
            .mem-list { list-style: none; display: flex; flex-direction: column; gap: 6px; max-height: 200px; overflow-y: auto; padding-right: 4px; }
            .mem-item { font-size: 12px; color: #D4D4D8; background: #27272A; padding: 8px 10px; border-radius: 6px; display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; line-height: 1.35; }
            .mem-del { color: #71717A; cursor: pointer; font-size: 13px; font-weight: bold; padding: 0 4px; border-radius: 4px; }
            .mem-del:hover { color: #EF4444; background: #3F3F46; }
            .mem-add-row { display: flex; gap: 6px; margin-top: 8px; }
            .mem-input { flex: 1; background: #27272A; border: 1px solid #3F3F46; border-radius: 6px; padding: 6px 8px; color: #FFF; font-size: 11px; outline: none; }
            .mem-btn { background: #3F3F46; color: #FF9900; border: none; border-radius: 6px; padding: 6px 10px; font-size: 11px; font-weight: bold; cursor: pointer; }
            .mem-btn:hover { background: #52525B; }

            /* Khung Chat chinh */
            .main { flex: 1; display: flex; flex-direction: column; background: #0F0F11; }
            .chat-header { padding: 14px 24px; border-bottom: 1px solid #27272A; display: flex; justify-content: space-between; align-items: center; }
            .chat-box { flex: 1; padding: 20px 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }
            
            .msg { max-width: 78%; padding: 12px 16px; border-radius: 12px; line-height: 1.5; font-size: 14px; white-space: pre-wrap; }
            .msg.user { align-self: flex-end; background: #27272A; color: #FFF; border-bottom-right-radius: 2px; }
            .msg.albert { align-self: flex-start; background: #18181B; border: 1px solid #2E2E33; color: #F4F4F5; border-bottom-left-radius: 2px; }
            .msg.albert .speaker { color: #FF9900; font-weight: 600; font-size: 12px; margin-bottom: 4px; display: block; }

            /* Khung nhap lieu */
            .input-area { padding: 16px 24px; border-top: 1px solid #27272A; display: flex; gap: 10px; align-items: center; }
            .input-box { flex: 1; background: #18181B; border: 1px solid #2E2E33; border-radius: 8px; padding: 12px 16px; color: #FFF; font-size: 14px; outline: none; }
            .input-box:focus { border-color: #FF9900; }
            .btn { background: #FF9900; color: #000; font-weight: 600; border: none; border-radius: 8px; padding: 12px 20px; cursor: pointer; transition: 0.2s; font-size: 13px; }
            .btn:hover { background: #FFAA22; }
            .btn-mic { background: #27272A; color: #E5E5E7; padding: 12px 14px; }
            .btn-mic.recording { background: #EF4444; color: #FFF; animation: pulse 1s infinite; }
            @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div class="brand">
                <h2>⚡ A.L.B.E.R.T.</h2>
                <p>Personal AI Advisor & Controller</p>
            </div>

            <!-- Ký ức Dài Hạn (Long-term Memory) -->
            <div class="card">
                <h4>🧠 KÝ ỨC DÀI HẠN <span style="font-size: 10px; color: #10B981; font-weight: normal;">● Đang bật</span></h4>
                <p style="font-size: 11px; color: #71717A; margin-bottom: 8px;">Albert tự động ghi nhớ thói quen, thông số và các dặn dò của bạn:</p>
                <ul class="mem-list" id="mem-list">
                    <li class="mem-item">Đang tải ký ức...</li>
                </ul>
                <div class="mem-add-row">
                    <input type="text" id="mem-in" class="mem-input" placeholder="Dặn dò Albert ghi nhớ điều gì..." onkeydown="if(event.key==='Enter') addMem()">
                    <button class="mem-btn" onclick="addMem()">+ Lưu</button>
                </div>
            </div>

            <!-- Phần cứng Relay -->
            <div class="card">
                <h4>Phần cứng Relay (ESP32-S3)</h4>
                <div class="relay-row">
                    <span class="relay-name">Relay 1 (GPIO 4 - Gia nhiệt)</span>
                    <span id="tag-r1" class="status-tag">OFF</span>
                </div>
                <div class="relay-row">
                    <span class="relay-name">Relay 2 (GPIO 5 - Quạt)</span>
                    <span id="tag-r2" class="status-tag">OFF</span>
                </div>
            </div>

            <!-- Giọng nói -->
            <div class="card">
                <h4>Giọng nói chuẩn J.A.R.V.I.S.</h4>
                <p style="font-size: 11px; color: #A1A1AA; line-height: 1.4;">
                    • <b>English:</b> Ryan (British RP)<br>
                    • <b>Tiếng Việt:</b> Nam Minh (Trầm ấm)
                </p>
            </div>

            <audio id="albert-player" style="display: none;"></audio>
        </div>

        <div class="main">
            <div class="chat-header">
                <div><b>Trực tuyến</b> <span style="color: #10B981;">● Online (Gemini Brain)</span></div>
                <div style="font-size: 12px; color: #71717A;">Cố vấn & Trợ lý cá nhân</div>
            </div>

            <div class="chat-box" id="chat">
                <div class="msg albert">
                    <span class="speaker">ALBERT</span>
                    Chào bạn. Tôi là Albert, trợ lý và cố vấn riêng của bạn. Hệ thống và bộ nhớ dài hạn đã sẵn sàng. Bạn cần tôi hỗ trợ điều gì hôm nay?
                </div>
            </div>

            <div class="input-area">
                <button class="btn btn-mic" id="mic-btn" onclick="toggleMic()">🎤 Nói</button>
                <input type="text" id="text-in" class="input-box" placeholder="Nhập câu hỏi, dặn dò hoặc ra lệnh (vd: 'Bật sấy', 'Nhớ là tôi hay sấy PETG ở 65 độ')..." onkeydown="if(event.key==='Enter') sendMsg()">
                <button class="btn" onclick="sendMsg()">Gửi</button>
            </div>
        </div>

        <script>
            const chat = document.getElementById('chat');
            const player = document.getElementById('albert-player');
            let recognition = null;
            let isRecording = false;

            // Load Memory ban dau
            fetchMemory();

            async function fetchMemory() {
                try {
                    const res = await fetch('/api/memory');
                    const data = await res.json();
                    const list = document.getElementById('mem-list');
                    list.innerHTML = '';
                    const facts = data.learned_facts || [];
                    if (facts.length === 0) {
                        list.innerHTML = '<li class="mem-item" style="color:#71717A">Chưa có ký ức riêng nào được lưu.</li>';
                        return;
                    }
                    facts.forEach((fact, idx) => {
                        const li = document.createElement('li');
                        li.className = 'mem-item';
                        li.innerHTML = `<span>• ${fact}</span><span class="mem-del" onclick="delMem(${idx})" title="Xóa ký ức này">×</span>`;
                        list.appendChild(li);
                    });
                } catch (e) {
                    console.error('Lỗi tải ký ức:', e);
                }
            }

            async function addMem() {
                const input = document.getElementById('mem-in');
                const text = input.value.trim();
                if (!text) return;
                await fetch('/api/memory/fact', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ fact: text })
                });
                input.value = '';
                fetchMemory();
            }

            async function delMem(index) {
                await fetch('/api/memory/fact/' + index, { method: 'DELETE' });
                fetchMemory();
            }

            // Web Speech Recognition
            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
                const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
                recognition = new SpeechRec();
                recognition.continuous = false;
                recognition.lang = 'vi-VN';
                recognition.onresult = (e) => {
                    const text = e.results[0][0].transcript;
                    document.getElementById('text-in').value = text;
                    sendMsg();
                };
                recognition.onend = () => {
                    isRecording = false;
                    document.getElementById('mic-btn').classList.remove('recording');
                };
            }

            function toggleMic() {
                if (!recognition) {
                    alert('Trình duyệt chưa hỗ trợ Web Speech. Vui lòng gõ tin nhắn.');
                    return;
                }
                if (isRecording) {
                    recognition.stop();
                } else {
                    recognition.start();
                    isRecording = true;
                    document.getElementById('mic-btn').classList.add('recording');
                }
            }

            async function sendMsg() {
                const input = document.getElementById('text-in');
                const text = input.value.trim();
                if (!text) return;

                appendMsg('user', text);
                input.value = '';

                try {
                    const res = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: text })
                    });
                    const data = await res.json();
                    
                    if (data.relay_action) {
                        const tag = document.getElementById('tag-' + (data.relay_action.target === 'relay_1' ? 'r1' : 'r2'));
                        if (data.relay_action.state === 1) {
                            tag.classList.add('active');
                            tag.innerText = 'ON';
                        } else {
                            tag.classList.remove('active');
                            tag.innerText = 'OFF';
                        }
                    }

                    appendMsg('albert', data.reply);

                    if (data.audio_url) {
                        player.src = data.audio_url + '?t=' + new Date().getTime();
                        player.play();
                    }

                    // Cap nhat lai bo nho sau vai giay neu co ky uc moi duoc trich xuat
                    setTimeout(fetchMemory, 2500);

                } catch (e) {
                    appendMsg('albert', 'Lỗi kết nối máy chủ: ' + e);
                }
            }

            function appendMsg(sender, text) {
                const div = document.createElement('div');
                div.className = 'msg ' + sender;
                if (sender === 'albert') {
                    div.innerHTML = '<span class="speaker">ALBERT</span>' + text;
                } else {
                    div.innerText = text;
                }
                chat.appendChild(div);
                chat.scrollTop = chat.scrollHeight;
            }
        </script>
    </body>
    </html>
    """

# ==============================================================================
# 2. API QUAN LY BO NHO DAI HAN (LONG-TERM MEMORY ENDPOINTS)
# ==============================================================================
@app.get("/api/memory")
async def api_get_memory():
    return JSONResponse(load_memory())

@app.post("/api/memory/fact")
async def api_add_fact(payload: dict):
    fact = payload.get("fact", "").strip()
    if fact:
        add_fact(fact)
    return {"status": "ok"}

@app.delete("/api/memory/fact/{index}")
async def api_delete_fact(index: int):
    success = delete_fact(index)
    return {"status": "ok" if success else "error"}

# ==============================================================================
# 3. API XU LY CHAT TRUC TIEP CHO WEB CONSOLE (GEMINI BRAIN + MEMORY)
# ==============================================================================
@app.post("/api/chat")
async def api_chat(payload: dict):
    user_text = payload.get("text", "").strip()
    if not user_text:
        return {"reply": "", "relay_action": None, "audio_url": None}

    response_text = ""
    relay_action = None

    try:
        # Goi Gemini Flash LLM voi System Prompt chua ca Bo Nho Dai Han
        ai_res = await call_gemini(user_text, conversation_history=chat_history)
        action = ai_res.get("action", "chat")
        relay_target = ai_res.get("relay_target")
        relay_state = ai_res.get("relay_state")
        search_query = ai_res.get("search_query")
        reply = ai_res.get("reply", "")

        # 1. Neu la lenh Relay
        if action == "relay" and relay_target:
            state_val = int(relay_state) if relay_state is not None else 1
            action_name = control_relay(relay_target, state_val)
            relay_action = {
                "target": relay_target,
                "state": state_val
            }
            response_text = reply if reply else f"Đã {action_name} {relay_target} thành công."

        # 2. Neu la lenh Search
        elif action == "search" and search_query:
            search_data = search_web(search_query)
            if reply:
                response_text = f"{reply}\n\n[Dữ liệu nghiên cứu: {search_data}]"
            else:
                response_text = f"Theo thông tin tôi tra cứu được: {search_data}"

        # 3. Tra loi hoi thoai / co van
        else:
            response_text = reply if reply else "Tôi đã ghi nhận thông tin."

    except Exception as e:
        print(f"[A.L.B.E.R.T. Server Error]: {e}")
        response_text = f"Tôi gặp sự cố khi xử lý yêu cầu: {e}"

    # Luu lich su hoi thoai
    chat_history.append({"role": "user", "content": user_text})
    chat_history.append({"role": "model", "content": response_text})
    if len(chat_history) > 12:
        chat_history.pop(0)
        chat_history.pop(0)

    # Sinh am thanh giong doc J.A.R.V.I.S.
    try:
        await speak_text(response_text, AUDIO_OUTPUT_PATH)
        audio_url = "/api/audio"
    except Exception as e:
        print(f"[A.L.B.E.R.T. Voice Error]: {e}")
        audio_url = None

    return {
        "reply": response_text,
        "relay_action": relay_action,
        "audio_url": audio_url
    }

@app.get("/api/audio")
async def get_audio():
    if os.path.exists(AUDIO_OUTPUT_PATH):
        return FileResponse(AUDIO_OUTPUT_PATH, media_type="audio/mpeg")
    return HTMLResponse("No audio", status_code=404)

# ==============================================================================
# 4. API AUDIO RAW (PCM 16-bit 16kHz) CHO ESP32 / MAX98357A
# ==============================================================================
@app.get("/api/audio/raw")
async def get_audio_raw():
    """
    Chuyển đổi MP3 → PCM 16-bit 16kHz để ESP32/MAX98357A phát trực tiếp.
    Yêu cầu: pip install pydub (cần ffmpeg trong PATH)
    Nếu không có pydub/ffmpeg → trả về MP3 gốc (ESP32 sẽ bị nhiễu)
    """
    if not os.path.exists(AUDIO_OUTPUT_PATH):
        return HTMLResponse("No audio", status_code=404)
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(AUDIO_OUTPUT_PATH)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        raw_path = AUDIO_OUTPUT_PATH.replace(".mp3", ".raw")
        audio.export(raw_path, format="raw")
        return FileResponse(raw_path, media_type="application/octet-stream")
    except ImportError:
        # Fallback: trả MP3 nếu chưa cài pydub
        return FileResponse(AUDIO_OUTPUT_PATH, media_type="audio/mpeg")
    except Exception as e:
        print(f"[Audio RAW] Lỗi chuyển đổi: {e}")
        return FileResponse(AUDIO_OUTPUT_PATH, media_type="audio/mpeg")

# ==============================================================================
# 5. API STT: ESP32 gửi raw PCM 32-bit 16kHz → Server nhận diện giọng nói → trả text
# ==============================================================================
@app.post("/api/stt")
async def api_stt(request):
    """
    ESP32 gửi HTTP POST raw audio (PCM 32-bit signed, 16kHz, MONO) lên đây.
    Server dùng Gemini Flash để nhận diện giọng nói → trả về JSON {text: "..."}
    """
    import base64
    import httpx

    raw_audio = await request.body()
    if not raw_audio or len(raw_audio) < 512:
        return JSONResponse({"text": "", "error": "audio too short"})

    print(f"[STT] Nhan {len(raw_audio)} bytes PCM tu ESP32, dang nhan dang...")

    try:
        # Chuyển PCM 32-bit → 16-bit để gửi Gemini
        import struct
        samples_32 = struct.unpack_from("<" + str(len(raw_audio) // 4) + "i", raw_audio)
        samples_16 = [max(-32768, min(32767, (s >> 8))) for s in samples_32]
        pcm16 = struct.pack("<" + str(len(samples_16)) + "h", *samples_16)

        # Encode base64 để gửi Gemini
        audio_b64 = base64.b64encode(pcm16).decode()

        # Gọi Gemini Flash với audio inline
        api_key = os.environ.get("GEMINI_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Hãy chuyển đoạn âm thanh sau sang văn bản tiếng Việt hoặc tiếng Anh. Chỉ trả về đúng văn bản nghe được, không giải thích thêm gì."},
                    {"inline_data": {"mime_type": "audio/l16;rate=16000", "data": audio_b64}}
                ]
            }],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 256}
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        print(f"[STT] Ket qua: '{text}'")
        return JSONResponse({"text": text})

    except Exception as e:
        print(f"[STT] Loi: {e}")
        return JSONResponse({"text": "", "error": str(e)})


# ==============================================================================
# 6. WEBSOCKET KET NOI ESP32 THUC TE
# ==============================================================================
@app.websocket("/ws/esp32")
async def websocket_esp32_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    print(f"[ESP32] Thiết bị kết nối: {websocket.client}")
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "")

            if msg_type == "hello":
                print(f"[ESP32] Device hello: {msg}")
                await websocket.send_text(json.dumps({
                    "type": "welcome",
                    "message": "Albert Server sẵn sàng"
                }))

            elif msg_type == "user_audio":
                print(f"[ESP32] User spoke: {msg.get('length_bytes', 0)} bytes")
                await websocket.send_text(json.dumps({
                    "type": "play_audio",
                    "url": f"http://{websocket.headers.get('host', SERVER_HOST + ':' + str(SERVER_PORT_NUM))}/api/audio/raw"
                }))

            elif msg_type == "pong":
                pass

    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)
        print("[ESP32] Thiết bị ngắt kết nối")
