# memory_manager.py - He thong quan ly bo nho dai han cho A.L.B.E.R.T.
import os
import json
import asyncio
import aiohttp

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")

def load_memory() -> dict:
    """Doc file bo nho tu dia"""
    if not os.path.exists(MEMORY_FILE):
        return {
            "user_profile": {},
            "hardware_and_projects": {},
            "learned_facts": []
        }
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Memory] Loi doc memory.json: {e}")
        return {"user_profile": {}, "hardware_and_projects": {}, "learned_facts": []}

def save_memory(data: dict):
    """Ghi file bo nho vao dia an toan"""
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("[Memory] Da cap nhat bo nho vao memory.json")
    except Exception as e:
        print(f"[Memory] Loi luu memory.json: {e}")

def format_memory_for_prompt() -> str:
    """Format bo nho thanh van ban ngan gon de tiem vao System Prompt"""
    mem = load_memory()
    lines = ["BỘ NHỚ DÀI HẠN VỀ NGƯỜI DÙNG & DỰ ÁN (HÃY LUÔN GHI NHỚ VÀ ÁP DỤNG):"]
    
    # 1. Profile nguoi dung
    profile = mem.get("user_profile", {})
    if profile:
        lines.append("- Đặc điểm người dùng:")
        for k, v in profile.items():
            lines.append(f"  • {v}")
            
    # 2. Phan cung & Du an
    hw = mem.get("hardware_and_projects", {})
    if hw:
        lines.append("- Thông tin phần cứng & Dự án liên quan:")
        for k, v in hw.items():
            lines.append(f"  • {k}: {v}")
            
    # 3. Cac dieu da hoc duoc
    facts = mem.get("learned_facts", [])
    if facts:
        lines.append("- Những điều người dùng đã dặn dò hoặc Albert đã ghi nhớ:")
        for f in facts[-25:]: # Giu toi da 25 facts gan nhat cho nhe context
            lines.append(f"  • {f}")
            
    return "\n".join(lines)

def add_fact(fact_text: str):
    """Them mot dieu can nho vao bo nho"""
    fact_text = fact_text.strip()
    if not fact_text:
        return
    mem = load_memory()
    if "learned_facts" not in mem:
        mem["learned_facts"] = []
    # Tranh trung lap
    if fact_text not in mem["learned_facts"]:
        mem["learned_facts"].append(fact_text)
        save_memory(mem)

def delete_fact(index: int) -> bool:
    """Xoa mot dieu can nho theo vi tri index"""
    mem = load_memory()
    facts = mem.get("learned_facts", [])
    if 0 <= index < len(facts):
        deleted = facts.pop(index)
        print(f"[Memory] Da xoa ky uc: {deleted}")
        mem["learned_facts"] = facts
        save_memory(mem)
        return True
    return False

# Trigger tu dong trich xuat ky uc bang AI (Background Task)
MEMORY_EXTRACT_PROMPT = """Bạn là module quản lý trí nhớ dài hạn của trợ lý A.L.B.E.R.T.
Hãy phân tích câu nói của người dùng.
NẾU câu nói chứa thông tin cá nhân mới, sở thích mới, thông số kỹ thuật mới, hoặc câu dặn dò (ví dụ: "nhớ là...", "tôi hay...", "tôi vừa đổi...", "thông số máy tôi là..."):
-> Hãy rút ra DUY NHẤT 1 câu sự thật ngắn gọn (dưới 20 chữ) cần lưu lại.
NẾU chỉ là câu trò chuyện xã giao, chào hỏi, hoặc lệnh điều khiển thông thường:
-> Trả về đúng chữ "NONE".

Chỉ trả về câu cần nhớ hoặc "NONE", không giải thích thêm."""

async def auto_extract_memory(user_text: str, api_key: str, candidate_models: list):
    """Tu dong phan tich va luu ky uc moi neu co"""
    # Loc nhanh: neu cau qua ngan duoi 4 tu thi bo qua khong can goi AI
    if len(user_text.strip().split()) < 4:
        return
        
    # Kiem tra cac tu khoa hay xuat hien khi nguoi dung muon dặn dò
    cue_words = ["nhớ", "tôi là", "tôi thích", "tôi hay", "tôi dùng", "máy của tôi", "dự án", "thông số", "đổi sang", "mua", "chuẩn của tôi"]
    has_cue = any(c in user_text.lower() for c in cue_words)
    if not has_cue:
        return

    payload = {
        "system_instruction": {"parts": [{"text": MEMORY_EXTRACT_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 60}
    }
    
    timeout = aiohttp.ClientTimeout(total=8)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for model_name in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                try:
                    async with session.post(url, json=payload, headers={"Content-Type": "application/json"}) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            extracted = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                            if extracted and extracted.upper() != "NONE" and len(extracted) < 150:
                                print(f"[Memory Extractor] Ghi nhận ký ức mới: '{extracted}'")
                                add_fact(extracted)
                            return
                except Exception:
                    continue
    except Exception as e:
        print(f"[Memory Extractor Error]: {e}")
