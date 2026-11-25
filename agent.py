# agent.py - Bo nao A.L.B.E.R.T. (Gemini Flash + Voice + Research + IoT Relay)
import os
import json
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime

# Load .env thu cong (khong can python-dotenv)
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

load_env()

# ==============================================================================
# 1. NAP QUY TAC TU FILE custom_rules.json
# ==============================================================================
RULES_FILE = os.path.join(os.path.dirname(__file__), "custom_rules.json")

def load_rules():
    with open(RULES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_rules()

# ==============================================================================
# 2. GEMINI FLASH LLM - BON NAO CHINH CUA A.L.B.E.R.T. (VOI AUTO-FALLBACK)
# ==============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
CANDIDATE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite"
]

import aiohttp
from memory_manager import format_memory_for_prompt, auto_extract_memory

def build_system_prompt() -> str:
    """Xay dung System Prompt dong bao gom ca Bo Nho Dai Han"""
    memory_text = format_memory_for_prompt()
    return f"""Bạn là A.L.B.E.R.T. (Always Listens, Browses facts, Explains clearly, Respects rules, and Toggles switches) — trợ lý và cố vấn riêng đắc lực của người dùng.

{memory_text}

PHONG CÁCH TƯ DUY & ỨNG XỬ:
- Thừa hưởng năng lực phân tích sâu sắc, tư duy logic, phản biện đa chiều chuẩn Claude
- Điềm tĩnh, lịch lãm, trầm ấm, khách quan như J.A.R.V.I.S.
- Tuyệt đối không nịnh bợ, không dài dòng sáo rỗng. Luôn dựa trên các thông tin trong BỘ NHỚ ĐÃ LƯU về người dùng để trả lời tinh tế, chuẩn xác
- Trả lời ngắn gọn, súc tích. Chỉ nói những gì cần thiết

THIẾT BỊ PHẦN CỨNG (ESP32-S3):
- Relay 1 (GPIO 4): Thiết bị gia nhiệt
- Relay 2 (GPIO 5): Quạt làm mát

PHÂN TÍCH Ý ĐỊNH - Trả về JSON với format:
{{
  "action": "chat" | "relay" | "search",
  "relay_target": "relay_1" | "relay_2" | null,
  "relay_state": 1 | 0 | null,
  "search_query": "từ khóa tìm kiếm" | null,
  "reply": "câu trả lời của Albert"
}}

Ví dụ:
- "Bật relay 1 lên" → {{"action":"relay","relay_target":"relay_1","relay_state":1,"search_query":null,"reply":"Đã bật Relay 1, thưa ngài."}}
- "Tìm thông số PETG" → {{"action":"search","relay_target":null,"relay_state":null,"search_query":"PETG filament specifications","reply":"Tôi đang tra cứu..."}}
- "Hôm nay thời tiết thế nào?" → {{"action":"chat","relay_target":null,"relay_state":null,"search_query":null,"reply":"Xin lỗi, tôi không có dữ liệu thời gian thực về thời tiết hiện tại."}}

QUAN TRỌNG: Chỉ trả về JSON thuần túy, không có markdown, không có ```json, không có giải thích thêm."""

async def call_gemini(user_text: str, conversation_history: list = None) -> dict:
    """Goi Gemini Flash API voi auto-fallback qua cac model neu bi 503/429"""
    if not GEMINI_API_KEY:
        return {"action": "chat", "relay_target": None, "relay_state": None, "search_query": None,
                "reply": "API key chưa được cấu hình. Vui lòng kiểm tra file .env"}

    contents = []
    if conversation_history:
        for turn in conversation_history[-6:]:
            contents.append({
                "role": turn["role"],
                "parts": [{"text": turn["content"]}]
            })

    contents.append({
        "role": "user",
        "parts": [{"text": user_text}]
    })

    payload = {
        "system_instruction": {
            "parts": [{"text": build_system_prompt()}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 512
        }
    }

    timeout = aiohttp.ClientTimeout(total=8)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for model_name in CANDIDATE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
            try:
                async with session.post(url, json=payload, headers={"Content-Type": "application/json"}) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if raw_text.startswith("```"):
                            raw_text = raw_text.split("```")[1]
                            if raw_text.startswith("json"):
                                raw_text = raw_text[4:]
                        parsed = json.loads(raw_text.strip())
                        # Kich hoat trich xuat ky uc dai han ngam (khong can cho)
                        asyncio.create_task(auto_extract_memory(user_text, GEMINI_API_KEY, CANDIDATE_MODELS))
                        return parsed
                    elif resp.status in (503, 429, 404):
                        print(f"[ALBERT LLM] Model {model_name} trả về HTTP {resp.status}, thử model kế tiếp...")
                        continue
                    else:
                        err_text = await resp.text()
                        print(f"[ALBERT LLM] Model {model_name} HTTP {resp.status}: {err_text[:200]}")
                        continue
            except json.JSONDecodeError as e:
                print(f"[ALBERT LLM] JSON parse error: {e}")
                return {"action": "chat", "relay_target": None, "relay_state": None, "search_query": None,
                        "reply": raw_text if 'raw_text' in locals() else "Lỗi xử lý phản hồi từ Gemini."}
            except Exception as e:
                print(f"[ALBERT LLM] Error with {model_name}: {repr(e)}, thử tiếp...")
                continue

    return {"action": "chat", "relay_target": None, "relay_state": None, "search_query": None,
            "reply": "Hiện tại các máy chủ Gemini đang quá tải, vui lòng thử lại sau giây lát."}

# ==============================================================================
# 3. CONG CU TRA CUU THONG TIN (RESEARCH TOOL - DUCKDUCKGO)
# ==============================================================================
def search_web(query: str, max_results: int = 3) -> str:
    """Tra cuu thong tin tren Internet"""
    print(f"[A.L.B.E.R.T. Research] Đang tìm kiếm: '{query}'...")
    try:
        clean_q = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={clean_q}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read().decode('utf-8', errors='ignore')
            if content.strip().startswith('{'):
                data = json.loads(content)
                abstract = data.get("AbstractText", "")
                if abstract:
                    return abstract
                topics = data.get("RelatedTopics", [])
                results = []
                for t in topics[:max_results]:
                    if isinstance(t, dict) and "Text" in t:
                        results.append("- " + t["Text"])
                if results:
                    return "\n".join(results)

        return f"Không tìm thấy dữ liệu tóm tắt cho '{query}'. Cần tra cứu chi tiết theo datasheet hoặc tài liệu nhà sản xuất."
    except Exception as e:
        return f"Lỗi tra cứu: {e}"

# ==============================================================================
# 4. CONG CU DIEU KHIEN THIET BI (RELAY CONTROL)
# ==============================================================================
RELAY_STATES = {
    "relay_1": False,
    "relay_2": False
}

def control_relay(relay_id: str, state: int) -> str:
    """Dieu khien bat/tat Relay tren ESP32-S3"""
    is_on = bool(state)
    target_relay = relay_id if relay_id in RELAY_STATES else "relay_1"

    device_info = CONFIG["hardware_devices"].get(target_relay, {})
    device_name = device_info.get("name", target_relay)
    gpio = device_info.get("gpio", 4)

    RELAY_STATES[target_relay] = is_on
    action_text = "BẬT" if is_on else "TẮT"
    print(f"[A.L.B.E.R.T. Hardware] {action_text} {device_name} (GPIO {gpio})")

    return action_text

# ==============================================================================
# 5. TAO GIONG NOI (EDGE-TTS) VOI AUTO-RETRY PITCH
# ==============================================================================
async def speak_text(text: str, output_path: str = "response.mp3", lang: str = "auto"):
    """Phat am thanh bang giong doc chuan J.A.R.V.I.S. voi auto-retry pitch khi bi tu choi"""
    try:
        import edge_tts
        import unicodedata
        speech_cfg = CONFIG.get("speech_settings", {})

        # Phat hien ngon ngu
        is_vietnamese = False
        if lang == "vi":
            is_vietnamese = True
        elif lang == "en":
            is_vietnamese = False
        else:
            vietnamese_chars = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
            is_vietnamese = any(c in vietnamese_chars for c in text.lower())

        if is_vietnamese:
            voice = speech_cfg.get("vietnamese_voice", "vi-VN-NamMinhNeural")
            preferred_pitch = speech_cfg.get("vietnamese_pitch", "-10Hz")
            rate = speech_cfg.get("vietnamese_rate", "-4%")
        else:
            voice = speech_cfg.get("english_voice", "en-GB-RyanNeural")
            preferred_pitch = speech_cfg.get("english_pitch", "-3Hz")
            rate = speech_cfg.get("english_rate", "-4%")

        # Chuan hoa Unicode va lam sach van ban
        clean_text = unicodedata.normalize('NFC', text)
        clean_text = clean_text.replace("*", "").replace("#", "").replace("[", "").replace("]", "").replace("`", "")
        clean_text = clean_text.strip()
        if not clean_text:
            return None

        # Thu tat ca pitch fallback - khong bao gio raise, luon tra ve path hoac None
        pitch_fallbacks = [preferred_pitch, "+5Hz", None]
        for i, pitch in enumerate(pitch_fallbacks):
            try:
                if pitch is not None:
                    communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
                else:
                    communicate = edge_tts.Communicate(clean_text, voice, rate=rate)
                await communicate.save(output_path)
                label = f"pitch={pitch}" if pitch else "pitch=default"
                print(f"[A.L.B.E.R.T. Voice] {voice} ({label}): OK")
                return output_path
            except Exception as e:
                label = f"pitch={pitch}" if pitch else "pitch=default"
                is_last = (i == len(pitch_fallbacks) - 1)
                print(f"[A.L.B.E.R.T. Voice] {label} lỗi: {type(e).__name__}: {e}")
                if is_last:
                    print("[A.L.B.E.R.T. Voice] Tất cả pitch đều thất bại, bỏ qua audio lần này.")
                    return None
                print(f"[A.L.B.E.R.T. Voice] Thử pitch tiếp theo...")
                continue

        return None

    except ImportError:
        print("[A.L.B.E.R.T. Voice] Chưa cài edge-tts")
        return None
    except Exception as e:
        print(f"[A.L.B.E.R.T. Voice] Lỗi ngoài ý muốn: {e}")
        return None

# ==============================================================================
# 6. TEST NHANH API KEY
# ==============================================================================
async def test_gemini_connection():
    print("=" * 60)
    print(f" KIỂM TRA KẾT NỐI GEMINI API")
    print("=" * 60)
    result = await call_gemini("Chào Albert, hệ thống đã sẵn sàng chưa?")
    print(f"Response: {result}")
    return result

if __name__ == "__main__":
    asyncio.run(test_gemini_connection())
