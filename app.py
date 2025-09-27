# app.py -- Digital Krishi Doctor (Landing inside Gradio + model/tts guards)
import os
import pathlib
import gradio as gr
from gtts import gTTS
import mimetypes
import tempfile
import io
from PIL import Image
import google.generativeai as genai
import pyttsx3
import requests
import sys

# ---------------- Config & constants ----------------
WEATHER_API_KEY = ""

LANGUAGE_MAP = {
    "hi": "hi", "en": "en", "bn": "bn", "mr": "mr",
    "ta": "ta", "te": "te", "pa": "pa", "gu": "gu",
    "kn": "kn", "or": "or"
}

# Control whether to try pyttsx3 (headless servers usually fail)
USE_PYTTSX3 = bool(int(os.environ.get("ENABLE_PYTTSX3", "0")))

# ---------------- Helpers ----------------
def _guess_mime(path):
    mt, _ = mimetypes.guess_type(path)
    return mt or "image/jpeg"

def _stream_or_text(response):
    try:
        if hasattr(response, "__iter__") and not isinstance(response, (str, bytes)):
            parts = []
            for chunk in response:
                part = getattr(chunk, "text", str(chunk))
                parts.append(part)
            return "".join(parts)
        return getattr(response, "text", str(response))
    except Exception as e:
        print("Error in _stream_or_text:", e)
        return f"[streaming error] {e}"

def _save_gtts_audio(text, lang_code):
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp_path = tmp.name
        tmp.close()
        gTTS(text=text, lang=lang_code).save(tmp_path)
        return tmp_path
    except Exception as e:
        print("gTTS failed:", e)
        return None

def _save_pyttsx3_audio(text, tmp_path):
    try:
        engine = pyttsx3.init()
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        return tmp_path
    except Exception as e:
        print("pyttsx3 failed:", e)
        return None

def _compress_image_to_bytes(image_path, quality=60, max_size=(1024,1024)):
    try:
        img = Image.open(image_path)
        img = img.convert("RGB")
        img.thumbnail(max_size)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        print("Image compression failed:", e)
        with open(image_path, "rb") as f:
            raw = f.read()
        return raw, _guess_mime(image_path)

# ---------------- Configure Gemini ----------------
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("WARNING: GEMINI_API_KEY environment variable not set.")
else:
    print("GEMINI_API_KEY found (length):", len(API_KEY))

try:
    genai.configure(api_key=API_KEY)
    print("genai.configure ok")
except Exception as e:
    print("genai.configure failed:", e)

# helper to list models (debug)
def list_available_models():
    try:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            print("list_models: GEMINI_API_KEY not set, skipping")
            return []
        r = requests.get(
            "https://generativelanguage.googleapis.com/v1/models",
            params={"key": key},
            timeout=20,
        )
        data = r.json()
        models = []
        if "models" in data:
            for m in data["models"]:
                name = m.get("name") or m.get("model") or m.get("id") or "<no-name>"
                models.append(name)
        print("list_models() ->", models)
        return models
    except Exception as e:
        print("list_models error:", e)
        return []

PREFERRED = [
    "models/gemini-2.5-flash",
    "gemini-2.5-flash",
    "models/gemini-2.5-pro",
    "gemini-2.5-pro",
    "models/gemini-2.0-flash",
    "gemini-2.0-flash",
]

AVAILABLE = list_available_models()

chosen = None
for cand in PREFERRED:
    try:
        print("Trying to create GenerativeModel with:", cand)
        m = genai.GenerativeModel(cand)
        chosen = (cand, m)
        print("Successfully created model object for:", cand)
        break
    except Exception as e:
        print("Could not create model for", cand, ":", e)

if chosen is None and AVAILABLE:
    for a in AVAILABLE:
        try:
            print("Trying available model:", a)
            m = genai.GenerativeModel(a)
            chosen = (a, m)
            print("Selected available model:", a)
            break
        except Exception as e:
            print("Failed to create model for", a, ":", e)

if chosen is None:
    print("ERROR: No usable model object could be created. Using dummy marker.")
    model = None
else:
    model = chosen[1]
    print("Using model identifier:", chosen[0])

MODEL_AVAILABLE = model is not None

def model_unavailable_response_text():
    return ("❌ AI model unavailable. Please set GEMINI_API_KEY correctly "
            "and ensure allowed model names. Admin se check karein.")

# ----------------- HANDLERS (with model-guard & pyttsx3 guard) -----------------
def handle_text_advisory(query, input_lang, output_lang):
    if not query:
        return "⚠️ Kripya sawaal likho.", ""
    if not MODEL_AVAILABLE:
        return model_unavailable_response_text(), ""
    prompt = f"Farmer question (language={input_lang}): {query}\nAnswer in {output_lang} language using simple, practical steps for smallholder farmers in India. Keep it concise with numbered actions; add safety notes for chemicals if any."
    try:
        resp = model.generate_content(prompt)
        reply = _stream_or_text(resp)
    except Exception as e:
        print("Error generating (text advisory):", e)
        return f"❌ Error generating response: {e}", ""
    tts_lang = LANGUAGE_MAP.get(output_lang, "en")
    audio_path = _save_gtts_audio(reply, tts_lang)
    if audio_path:
        return reply, audio_path
    if USE_PYTTSX3:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp_path = tmp.name
        tmp.close()
        if _save_pyttsx3_audio(reply, tmp_path):
            return reply, tmp_path
    return reply, ""

def handle_image_diagnosis(image, note, input_lang, output_lang):
    if image is None:
        return "⚠️ Kripya pehle image upload karo.", ""
    if not MODEL_AVAILABLE:
        return model_unavailable_response_text(), ""
    prompt = f"Diagnose the crop disease or pest from the image. Farmer note (language={input_lang}): {note or 'N/A'}.\nGive name of likely disease/pest, confidence, and immediate steps. Answer in {output_lang} language, with simple farmer-friendly bullet points and safety precautions."
    img_bytes, mime_type = _compress_image_to_bytes(image, quality=60)
    try:
        resp = model.generate_content(
            contents=[{"role": "user", "parts":[{"text": prompt},{"inline_data":{"mime_type": mime_type,"data": img_bytes}}]}]
        )
        reply = _stream_or_text(resp)
    except Exception as e:
        print("Error generating (image diagnosis):", e)
        return f"❌ Error generating response: {e}", ""
    tts_lang = LANGUAGE_MAP.get(output_lang, "en")
    audio_path = _save_gtts_audio(reply, tts_lang)
    if audio_path:
        return reply, audio_path
    if USE_PYTTSX3:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp_path = tmp.name
        tmp.close()
        if _save_pyttsx3_audio(reply, tmp_path):
            return reply, tmp_path
    return reply, ""

def handle_voice(flow_audio, input_lang, output_lang):
    if flow_audio is None:
        return "Kuch suna nahi gaya.", "Kuch suna nahi gaya.", ""
    # Placeholder: implement real speech-to-text if you add it later
    heard_text = "[Placeholder recognized text from audio]"
    reply = f"[Voice reply in {output_lang}] Aapne kaha: {heard_text}"
    tts_lang = LANGUAGE_MAP.get(output_lang, "en")
    audio_path = _save_gtts_audio(reply, tts_lang)
    if audio_path:
        return heard_text, reply, audio_path
    if USE_PYTTSX3:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp_path = tmp.name
        tmp.close()
        if _save_pyttsx3_audio(reply, tmp_path):
            return heard_text, reply, tmp_path
    return heard_text, reply, ""

def get_weather(location):
    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo_res = requests.get(geo_url, params={"name": location, "count":1,"language":"en","format":"json"}, timeout=8).json()
        if not geo_res.get("results"):
            return f"⚠️ Location '{location}' ke liye data nahi mila."
        lat = geo_res["results"][0]["latitude"]
        lon = geo_res["results"][0]["longitude"]
        place_name = geo_res["results"][0]["name"]
        weather_url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": lat, "longitude": lon, "current_weather": True, "timezone":"Asia/Kolkata"}
        w_res = requests.get(weather_url, params=params, timeout=8).json()
        cw = w_res.get("current_weather")
        if not cw:
            return "⚠️ Mausam ki jankari uplabdh nahi hai."
        temp = cw.get("temperature")
        wind = cw.get("windspeed")
        weather_code = cw.get("weathercode")
        code_map = {0:"Clear sky",1:"Mainly clear",2:"Partly cloudy",3:"Overcast",45:"Fog",48:"Depositing rime fog",51:"Light drizzle",61:"Slight rain",71:"Slight snow",80:"Rain showers",95:"Thunderstorm"}
        weather_desc = code_map.get(weather_code,"Unknown condition")
        return f"📍 {place_name}\n🌦 Mausam: {weather_desc}\n🌡 Temp: {temp}°C\n💨 Hawa: {wind} km/h"
    except Exception as e:
        return f"❌ Error (Weather fetch): {e}"

def handle_location_advisory(location, query, input_lang, output_lang):
    if not location or not query:
        return "⚠️ Location aur sawaal dono zaroori hain.", ""
    if not MODEL_AVAILABLE:
        return model_unavailable_response_text(), ""
    weather_info = get_weather(location)
    try:
        prompt = f"Location: {location}\nWeather Info: {weather_info}\nFarmer Question (lang={input_lang}): {query}\nAnswer in {output_lang} language, simple words for farmers. Add crop/weather-specific practical tips."
        response = model.generate_content(prompt)
        reply = _stream_or_text(response)
    except Exception as e:
        print("Error generating (location advisory):", e)
        return f"❌ Error generating response: {e}", ""
    tts_lang = LANGUAGE_MAP.get(output_lang, "en")
    audio_path = _save_gtts_audio(reply, tts_lang)
    if audio_path:
        return reply, audio_path
    if USE_PYTTSX3:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp_path = tmp.name
        tmp.close()
        if _save_pyttsx3_audio(reply, tmp_path):
            return reply, tmp_path
    return reply, ""

def handle_fertilizer_calc(crop, area, area_unit, ph, nitrogen, phosphorus, potassium, input_lang, output_lang):
    if not crop or not area:
        return "⚠️ Kripya crop aur area ka data dijiye.", ""
    if not MODEL_AVAILABLE:
        return model_unavailable_response_text(), ""
    try:
        prompt = f"Crop: {crop}\nArea: {area} {area_unit}\nSoil Data → pH: {ph}, N: {nitrogen}, P: {phosphorus}, K: {potassium}\nGive explicit fertilizer recommendation (quantities in kg per {area_unit}) for {crop}. Include split doses (basal + top dressing) if relevant. Add alternatives like organic manure. Explain in {output_lang} language, with clear step-by-step guidance."
        resp = model.generate_content(prompt)
        reply = _stream_or_text(resp)
    except Exception as e:
        print("Error generating (fertilizer):", e)
        return f"❌ Error generating response: {e}", ""
    tts_lang = LANGUAGE_MAP.get(output_lang, "en")
    audio_path = _save_gtts_audio(reply, tts_lang)
    if audio_path:
        return reply, audio_path
    if USE_PYTTSX3:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp_path = tmp.name
        tmp.close()
        if _save_pyttsx3_audio(reply, tmp_path):
            return reply, tmp_path
    return reply, ""

# ----------------- UI: Landing inside Gradio + App -----------------
# Try both 'public' and 'Public' directories for compatibility
index_path_candidates = [
    pathlib.Path(__file__).parent.joinpath("public", "index.html"),
    pathlib.Path(__file__).parent.joinpath("Public", "index.html"),
]
LANDING_HTML_CONTENT = "<div style='padding:20px;text-align:center;'><h1>🌾 KRISHI BANDHU</h1></div>"
for p in index_path_candidates:
    if p.exists():
        try:
            LANDING_HTML_CONTENT = p.read_text(encoding="utf-8")
            print("Using landing from:", str(p))
            break
        except Exception as e:
            print("Failed to read landing file:", e)

with gr.Blocks(title="KRISHI BANDHU - Prototype (Phase 2)", elem_id="main_container", theme=gr.themes.Soft()) as demo:

    # Optional background CSS
    gr.HTML("""
    <style>
    #main_container { background-color: #437628e8; }
    </style>
    """)

    # Header (kept simple; landing below will show full index content)
    gr.HTML(f"""
    <div style="background:#437628e8; padding:12px; border-radius:8px; text-align:center; color:white; font-family:sans-serif;">
        <h2 style="margin:6px 0;">🌾 KRISHI BANDHU</h2>
    </div>
    """)

    # Landing (visible by default)
    with gr.Column(visible=True) as landing_container:
        gr.HTML(LANDING_HTML_CONTENT)
        # IMPORTANT: elem_id must match the id used by index.html onclick
        open_btn = gr.Button("Start Smart Farming", variant="primary", elem_id="open_gradio_button")

    # App container (hidden by default) - paste your app UI here
    with gr.Column(visible=False) as app_container:
        input_lang = gr.Dropdown(label="Input Language", choices=list(LANGUAGE_MAP.keys()), value="hi")
        output_lang = gr.Dropdown(label="Output Language", choices=list(LANGUAGE_MAP.keys()), value="hi")

        with gr.Tabs():
            with gr.TabItem("💬 Advisory Chat"):
                q = gr.Textbox(label="Farmer question", lines=3, placeholder="Aapka sawaal yahan likhein...")
                out_text = gr.Markdown()
                out_audio = gr.Audio(label="TTS output", interactive=False, type="filepath")
                btn = gr.Button("Get Advice", variant="primary")
                btn.click(handle_text_advisory, inputs=[q, input_lang, output_lang], outputs=[out_text, out_audio])

            with gr.TabItem("🖼️ Pest/Disease by Photo"):
                img = gr.Image(type="filepath", label="Upload crop/pest image")
                note = gr.Textbox(label="Extra note", placeholder="Jaise: gehun, 20 din, peele daag...")
                out_text2 = gr.Markdown()
                out_audio2 = gr.Audio(label="TTS output", interactive=False, type="filepath")
                btn2 = gr.Button("Diagnose", variant="primary")
                btn2.click(handle_image_diagnosis, inputs=[img, note, input_lang, output_lang], outputs=[out_text2, out_audio2])

            with gr.TabItem("🎙️ Voice Bot"):
                mic = gr.Audio(sources=["microphone"], type="filepath", label="Hold mic & speak")
                heard = gr.Textbox(label="Heard text")
                voice_reply = gr.Markdown()
                out_audio_voice = gr.Audio(label="TTS output", interactive=False, type="filepath")
                btn3 = gr.Button("Ask by Voice", variant="primary")
                btn3.click(handle_voice, inputs=[mic, input_lang, output_lang], outputs=[heard, voice_reply, out_audio_voice])

            with gr.TabItem("🌍 Location Advisory"):
                loc = gr.Textbox(label="Location", placeholder="District/City/Pincode")
                q2 = gr.Textbox(label="Farmer question", lines=3)
                out_text3 = gr.Markdown()
                out_audio_loc = gr.Audio(label="TTS output", interactive=False, type="filepath")
                btn4 = gr.Button("Get Location-based Advice", variant="primary")
                btn4.click(handle_location_advisory, inputs=[loc, q2, input_lang, output_lang], outputs=[out_text3, out_audio_loc])

            with gr.TabItem("🌱 Fertilizer Calculator"):
                crop = gr.Textbox(label="Crop Name", placeholder="e.g. Paddy, Wheat, Maize")
                area = gr.Textbox(label="Area", placeholder="e.g. 1")
                area_unit = gr.Dropdown(label="Area Unit", choices=["acre", "hectare"], value="acre")
                ph2 = gr.Textbox(label="Soil pH (optional)")
                n2 = gr.Textbox(label="Nitrogen (optional)")
                p2 = gr.Textbox(label="Phosphorus (optional)")
                k2 = gr.Textbox(label="Potassium (optional)")
                out_text5 = gr.Markdown()
                out_audio5 = gr.Audio(label="TTS output", interactive=False, type="filepath")
                btn6 = gr.Button("Get Fertilizer Plan", variant="primary")
                btn6.click(handle_fertilizer_calc, inputs=[crop, area, area_unit, ph2, n2, p2, k2, input_lang, output_lang], outputs=[out_text5, out_audio5])

    # Toggle function: hide landing, show app
    def open_app():
        return gr.update(visible=False), gr.update(visible=True)

    open_btn.click(open_app, inputs=None, outputs=[landing_container, app_container])

# ----------------- Launch -----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Gradio on 0.0.0.0:{port} (landing in Gradio). MODEL_AVAILABLE={MODEL_AVAILABLE}, USE_PYTTSX3={USE_PYTTSX3}")
    demo.launch(server_name="0.0.0.0", server_port=port, share=False)
