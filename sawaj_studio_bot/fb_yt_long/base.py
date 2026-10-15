"""Shared base module for long video"""
import os
import re
import time
import html
import random
import math
import base64
import subprocess
import shutil
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


class Config:
    TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID")
    _FB = os.environ.get("FACEBOOK_META_TOKEN", "").strip()
    _IG = os.environ.get("FACEBOOK_INSTAGRAM_META_TOKEN", "").strip()
    META = _FB or _IG
    PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "").strip()
    YT_CID = os.environ.get("YOUTUBE_CLIENT_ID")
    YT_CS = os.environ.get("YOUTUBE_CLIENT_SECRET")
    YT_RT = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    YT_PLID = os.environ.get("DAILY_HADITH_YT_PLAYLIST_ID")
    EVENT = os.environ.get("GITHUB_EVENT_NAME", "")
    MODE = os.environ.get("UPLOAD_MODE", "offline").strip().lower()
    CONFIRMED = str(os.environ.get("UPLOAD_CONFIRMED", "false")).lower() == "true"
    @property
    def scheduled(self):
        return self.EVENT == "schedule"
    @property
    def post_social(self):
        if self.scheduled:
            return True
        if self.MODE == "online":
            return self.CONFIRMED
        return False
    def platforms(self):
        a = []
        if self.META and self.PAGE_ID:
            a.append("facebook")
        if self.YT_RT and self.YT_CID:
            a.append("youtube")
        return a


_sess = requests.Session()
_buf = []
_cnt = {"t": 0, "ok": 0, "w": 0, "f": 0}
_t0 = None
_hdr = "RUN"


def _now():
    return datetime.now().strftime("%H:%M:%S")


def _esc(t):
    return html.escape(str(t), quote=False)


def log(m, l="INFO"):
    print("[" + _now() + "] [" + l + "] " + str(m), flush=True)


def _tg(m, silent=False):
    tok = Config.TG_TOKEN
    chat = Config.TG_CHAT
    if not (tok and chat):
        print(m)
        return
    if len(m) > 3900:
        m = m[:3900]
    try:
        _sess.post("https://api.telegram.org/bot" + tok + "/sendMessage",
            json={"chat_id": chat, "text": m, "parse_mode": "HTML",
                  "disable_web_page_preview": True,
                  "disable_notification": silent}, timeout=15)
    except Exception:
        pass


def run_start(t=None):
    global _t0, _hdr, _buf
    if t:
        _hdr = t
    _t0 = time.time()
    _buf = []
    for k in _cnt:
        _cnt[k] = 0
    _tg("STARTED: " + _esc(_hdr) + " at " + _now(), silent=True)


def header(t):
    _buf.append("\n=== " + _esc(t) + " ===")


def log_api(n, api, s, d=""):
    ic = {"success": "UP", "failed": "DOWN", "fallback": "FALLBACK", "skipped": "SKIP"}.get(s, "?")
    line = ic + ": " + _esc(api) + " [" + s.upper() + "]"
    if d:
        line += " - " + _esc(d)
    _buf.append(line)


def log_error(n, e):
    _cnt["f"] += 1
    _buf.append("ERROR: " + _esc(n) + ": " + _esc(str(e)[:150]))


def send_report():
    tt = time.time() - (_t0 or time.time())
    full = "<b>" + _esc(_hdr) + "</b>\n" + _now() + " - " + str(round(tt, 1)) + "s\n"
    full += "\n".join(_buf)
    chunks = []
    cur = ""
    for line in full.split("\n"):
        if len(cur) + len(line) + 1 > 3800:
            chunks.append(cur)
            cur = line
        else:
            cur += ("\n" if cur else "") + line
    if cur:
        chunks.append(cur)
    for i, c in enumerate(chunks, 1):
        pre = "Report " + str(i) + "/" + str(len(chunks)) + "\n" if len(chunks) > 1 else ""
        _tg(pre + c)
    _tg("DONE - Files: " + str(_cnt["t"]) + " OK: " + str(_cnt["ok"]) + " WARN: " + str(_cnt["w"]) + " FAIL: " + str(_cnt["f"]))


def sanitize(t):
    if not t:
        return ""
    t = re.sub(r"[\u200b-\u200f\ufeff\u202a-\u202e]", "", str(t))
    return t.replace('"', "").replace("'", "").replace("\n", " ").strip()


class BasePipeline:
    def __init__(self):
        self.cfg = Config()
        self.session = requests.Session()
        r = Retry(total=5, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=r))
        self.session.headers.update({"User-Agent": "SawajBot/3.0"})
    def run_cmd(self, cmd):
        log("CMD: " + cmd[:80])
        subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True, timeout=1800)
    def download(self, url, path, min_size=12000, retries=2):
        for _ in range(retries):
            try:
                r = self.session.get(url, timeout=60, stream=True)
                if r.status_code != 200:
                    continue
                w = 0
                with open(path, "wb") as f:
                    for c in r.iter_content(65536):
                        if not c:
                            continue
                        w += len(c)
                        if w > 200 * 1024 * 1024:
                            return False
                        f.write(c)
                if w > min_size:
                    return True
            except Exception:
                pass
        return False
    def cleanup(self, files, folder=None):
        for f in files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass
        if folder and os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)


BOOKS = [
    {"eng": "eng-bukhari", "ara": "ara-bukhari", "name": "Sahih al-Bukhari", "max": 7000},
    {"eng": "eng-muslim", "ara": "ara-muslim", "name": "Sahih Muslim", "max": 5000},
]
FALLBACK = {"collection": "Sahih al-Bukhari", "number": "1",
    "english": "The reward of deeds depends upon the intentions and every person will get the reward according to what he has intended.",
    "arabic": "Innamal aamalu bin niyyat",
    "book": "Sahih al-Bukhari", "hadith_no": "1", "narrator": "", "chapter": ""}


class Hadith:
    def __init__(self, base, min_w=400, max_w=1800):
        self.base = base
        self.min_w = min_w
        self.max_w = max_w
    def _one(self, url, book, n):
        try:
            r = self.base.session.get(url + "/editions/" + book["eng"] + "/" + str(n) + ".json", timeout=15)
            if r.status_code != 200:
                return None
            h = r.json().get("hadiths", [])
            if not h:
                return None
            eng = sanitize(h[0].get("text", ""))
            if len(eng) < 30:
                return None
            ar = ""
            try:
                ar_r = self.base.session.get(url + "/editions/" + book["ara"] + "/" + str(n) + ".json", timeout=10)
                if ar_r.status_code == 200:
                    ad = ar_r.json().get("hadiths", [])
                    if ad:
                        ar = sanitize(ad[0].get("text", ""))
            except Exception:
                pass
            num = str(h[0].get("hadithnumber") or n)
            return {"collection": book["name"], "number": num, "english": eng, "arabic": ar,
                    "book": book["name"], "hadith_no": num, "narrator": "", "chapter": ""}
        except Exception:
            return None
    def fetch(self):
        bases = []
        if os.environ.get("HADITH_API_URL"):
            bases.append(os.environ["HADITH_API_URL"].rstrip("/"))
        bases.append("https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1")
        bases.append("https://raw.githubusercontent.com/fawazahmed0/hadith-api/1")
        for _ in range(40):
            b = random.choice(BOOKS)
            n = random.randint(1, b["max"])
            for bu in bases:
                h = self._one(bu, b, n)
                if h:
                    wc = len(h["english"].split())
                    if self.min_w <= wc <= self.max_w:
                        log_api("hadith", "API", "success", str(wc) + "w")
                        return h
        log_api("hadith", "API", "fallback", "hardcoded")
        return FALLBACK


class AIProvider:
    def __init__(self, base):
        self.base = base
    def call(self, prompt, max_tokens=400, task="general"):
        s = self.base.session
        for name, fn in self._build():
            try:
                t = fn(s, prompt, max_tokens)
                if t:
                    log_api("ai", name + "/" + task, "success", str(len(t)) + "c")
                    return t
            except Exception as e:
                log_api("ai", name + "/" + task, "failed", str(e)[:60])
        log_api("ai", "ALL/" + task, "failed", "none worked")
        return ""
    def _build(self):
        p = []
        e = os.environ
        if e.get("OPENROUTER_API_KEY"):
            p.append(("OpenRouter", lambda s, q, m: self._oai(s, "https://openrouter.ai/api/v1/chat/completions", e["OPENROUTER_API_KEY"], "openai/gpt-4o-mini", q, m)))
        if e.get("GROQ_API_KEY"):
            p.append(("Groq", lambda s, q, m: self._oai(s, "https://api.groq.com/openai/v1/chat/completions", e["GROQ_API_KEY"], "llama-3.3-70b-versatile", q, m)))
        if e.get("GEMINI_API_KEY"):
            p.append(("Gemini", self._gem))
        if e.get("MISTRAL_API_KEY"):
            p.append(("Mistral", lambda s, q, m: self._oai(s, "https://api.mistral.ai/v1/chat/completions", e["MISTRAL_API_KEY"], "mistral-small-latest", q, m)))
        if e.get("CEREBRAS_API_KEY"):
            p.append(("Cerebras", lambda s, q, m: self._oai(s, "https://api.cerebras.ai/v1/chat/completions", e["CEREBRAS_API_KEY"], "llama3.1-8b", q, m)))
        if e.get("COHERE_API_KEY"):
            p.append(("Cohere", self._coh))
        if e.get("NVIDIA_API_KEY"):
            p.append(("NVIDIA", lambda s, q, m: self._oai(s, "https://integrate.api.nvidia.com/v1/chat/completions", e["NVIDIA_API_KEY"], "meta/llama-3.1-70b-instruct", q, m)))
        if e.get("HUGGINGFACE_API_KEY"):
            p.append(("HuggingFace", self._hf))
        if e.get("JINA_API_KEY"):
            p.append(("Jina", lambda s, q, m: self._oai(s, "https://api.jina.ai/v1/chat/completions", e["JINA_API_KEY"], "jina-chat-v1", q, m)))
        if e.get("TAVILY_API_KEY_AI"):
            p.append(("Tavily", self._tav))
        if e.get("DEEPAI_API_KEY"):
            p.append(("DeepAI", self._dai))
        if e.get("POLLINATIONS_API_URL"):
            p.append(("Pollinations", self._pol))
        if e.get("TOKEN_GITHUB"):
            p.append(("GitHubModels", self._ghm))
        return p
    def _oai(self, s, url, key, model, prompt, mt):
        r = s.post(url, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.6, "max_tokens": mt}, timeout=60)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        raise Exception("HTTP " + str(r.status_code))
    def _gem(self, s, prompt, mt):
        k = os.environ["GEMINI_API_KEY"]
        r = s.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + k,
            json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        raise Exception("HTTP " + str(r.status_code))
    def _coh(self, s, prompt, mt):
        k = os.environ["COHERE_API_KEY"]
        r = s.post("https://api.cohere.com/v1/chat",
            headers={"Authorization": "Bearer " + k, "Content-Type": "application/json"},
            json={"model": "command-r-plus", "message": prompt}, timeout=60)
        if r.status_code == 200:
            return r.json().get("text", "").strip()
        raise Exception("HTTP " + str(r.status_code))
    def _hf(self, s, prompt, mt):
        k = os.environ["HUGGINGFACE_API_KEY"]
        r = s.post("https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct",
            headers={"Authorization": "Bearer " + k, "Content-Type": "application/json"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": mt, "temperature": 0.6, "return_full_text": False}}, timeout=90)
        if r.status_code == 200:
            d = r.json()
            if isinstance(d, list) and d:
                return d[0].get("generated_text", "").strip()
            if isinstance(d, dict):
                return d.get("generated_text", "").strip()
        raise Exception("HTTP " + str(r.status_code))
    def _tav(self, s, prompt, mt):
        k = os.environ["TAVILY_API_KEY_AI"]
        r = s.post("https://api.tavily.com/search",
            json={"api_key": k, "query": prompt[:380], "search_depth": "advanced",
                  "include_answer": True, "max_results": 3}, timeout=60)
        if r.status_code == 200:
            a = r.json().get("answer", "").strip()
            if a:
                return a
        raise Exception("HTTP " + str(r.status_code))
    def _dai(self, s, prompt, mt):
        k = os.environ["DEEPAI_API_KEY"]
        r = s.post("https://api.deepai.org/api/text-generator",
            headers={"api-key": k}, data={"text": prompt[:380]}, timeout=60)
        if r.status_code == 200:
            o = r.json().get("output", "")
            if o:
                return str(o).strip()
        raise Exception("HTTP " + str(r.status_code))
    def _pol(self, s, prompt, mt):
        base = os.environ.get("POLLINATIONS_API_URL", "https://text.pollinations.ai")
        r = s.post(base.rstrip("/") + "/openai", headers={"Content-Type": "application/json"},
            json={"model": "openai", "messages": [{"role": "user", "content": prompt}]}, timeout=60)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        raise Exception("HTTP " + str(r.status_code))
    def _ghm(self, s, prompt, mt):
        k = os.environ["TOKEN_GITHUB"]
        r = s.post("https://models.inference.ai.azure.com/chat/completions",
            headers={"Authorization": "Bearer " + k, "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.6, "max_tokens": mt}, timeout=60)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        raise Exception("HTTP " + str(r.status_code))


class TTS:
    VOICE = {"hi": "hi-IN-MadhurNeural", "ar": "ar-SA-HamedNeural", "en": "en-US-ChristopherNeural"}
    def __init__(self, base):
        self.base = base
    def generate(self, text, out, lang="hi"):
        if not text or not text.strip():
            return False
        text = sanitize(text)
        if os.environ.get("SARVAM_API_KEY") and self._sar(text, out, lang):
            return True
        if os.environ.get("ELEVENLABS_API_KEY") and self._11l(text, out):
            return True
        if os.environ.get("VOICECAFE_API_URL") and self._vc(text, out, lang):
            return True
        if self._edge(text, out, lang):
            return True
        return self._gtts(text, out, lang)
    def _sar(self, text, out, lang):
        try:
            k = os.environ["SARVAM_API_KEY"]
            chunks = []
            for i in range(0, len(text), 450):
                chunks.append(text[i:i + 450])
            r = self.base.session.post("https://api.sarvam.ai/text-to-speech",
                headers={"api-subscription-key": k, "Content-Type": "application/json"},
                json={"inputs": chunks, "target_language_code": lang + "-IN",
                      "speaker": "meera", "pitch": 0, "pace": 0.85,
                      "loudness": 1.2, "speech_sample_rate": 22050,
                      "enable_preprocessing": True, "model": "bulbul:v1"}, timeout=120)
            if r.status_code == 200:
                a = r.json().get("audios", [])
                if a:
                    with open(out, "wb") as f:
                        f.write(base64.b64decode(a[0]))
                    log_api("tts", "Sarvam", "success")
                    return True
        except Exception as e:
            log_api("tts", "Sarvam", "failed", str(e)[:60])
        return False
    def _11l(self, text, out):
        try:
            r = self.base.session.post("https://api.elevenlabs.io/v1/text-to-speech/pNInz6obpgDQGcFmaJgB",
                headers={"Accept": "audio/mpeg", "Content-Type": "application/json",
                         "xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
                json={"text": text, "model_id": "eleven_multilingual_v2",
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.85}}, timeout=180)
            if r.status_code == 200 and len(r.content) > 5000:
                with open(out, "wb") as f:
                    f.write(r.content)
                log_api("tts", "11Labs", "success")
                return True
        except Exception as e:
            log_api("tts", "11Labs", "failed", str(e)[:60])
        return False
    def _vc(self, text, out, lang):
        try:
            base = os.environ["VOICECAFE_API_URL"].rstrip("/")
            r = self.base.session.post(base + "/api/tts",
                json={"text": text[:1000], "language": lang, "voice": "default", "format": "mp3"}, timeout=120)
            if r.status_code == 200 and len(r.content) > 5000:
                with open(out, "wb") as f:
                    f.write(r.content)
                log_api("tts", "VoiceCafe", "success")
                return True
        except Exception as e:
            log_api("tts", "VoiceCafe", "failed", str(e)[:60])
        return False
    def _edge(self, text, out, lang):
        tmp = out + ".txt"
        try:
            v = self.VOICE.get(lang, "hi-IN-MadhurNeural")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            cmd = 'edge-tts --file "' + tmp + '" --write-media "' + out + '" --voice ' + v + ' --rate=-12% --pitch=-5Hz --volume=+8%'
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
            if os.path.exists(out) and os.path.getsize(out) > 1000:
                log_api("tts", "edge", "success")
                return True
        except Exception:
            pass
        finally:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
        return False
    def _gtts(self, text, out, lang):
        try:
            from gtts import gTTS
            safe_lang = lang if lang in ("hi", "ar", "en") else "hi"
            gTTS(text=text, lang=safe_lang, slow=False).save(out)
            log_api("tts", "gTTS", "success")
            return True
        except Exception as e:
            log_api("tts", "gTTS", "failed", str(e)[:60])
            return False


class Music:
    def __init__(self, base):
        self.base = base
    def get(self, duration=60, out="music.mp3"):
        raw = out + ".raw"
        if self._fs(raw) and self._post(raw, out, duration):
            try:
                os.remove(raw)
            except Exception:
                pass
            return out
        if self._px(raw) and self._post(raw, out, duration):
            try:
                os.remove(raw)
            except Exception:
                pass
            return out
        if self._sine(out, duration):
            return out
        return None
    def _fs(self, out):
        k = os.environ.get("FREESOUND_API_KEY")
        if not k:
            return False
        try:
            r = self.base.session.get("https://freesound.org/apiv2/search/text/",
                params={"query": "ambient islamic", "token": k,
                        "fields": "id,previews",
                        "filter": "duration:[30 TO 300]", "page_size": 5}, timeout=20)
            if r.status_code != 200:
                return False
            for it in r.json().get("results", []):
                u = it.get("previews", {}).get("preview-hq-mp3")
                if not u:
                    continue
                a = self.base.session.get(u, timeout=60)
                if a.status_code == 200 and len(a.content) > 20000:
                    with open(out, "wb") as f:
                        f.write(a.content)
                    log_api("music", "Freesound", "success")
                    return True
        except Exception:
            pass
        return False
    def _px(self, out):
        url = "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a73467.mp3"
        try:
            r = self.base.session.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 20000:
                with open(out, "wb") as f:
                    f.write(r.content)
                log_api("music", "Pixabay", "success")
                return True
        except Exception:
            pass
        return False
    def _post(self, raw, out, dur):
        if not os.path.exists(raw) or os.path.getsize(raw) < 5000:
            return False
        fo = max(0.1, dur - 5.0)
        cmd = 'ffmpeg -y -stream_loop -1 -i "' + raw + '" -t ' + str(dur) + ' -af "volume=0.22,afade=t=in:st=0:d=2,afade=t=out:st=' + str(round(fo, 2)) + ':d=5" -c:a libmp3lame -b:a 128k "' + out + '"'
        try:
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            return os.path.exists(out) and os.path.getsize(out) > 10000
        except Exception:
            return False
    def _sine(self, out, dur):
        fo = max(0.1, dur - 5.0)
        cmd = 'ffmpeg -y -f lavfi -i "sine=frequency=220:duration=' + str(dur) + '" -af "volume=0.15,afade=t=in:st=0:d=2,afade=t=out:st=' + str(round(fo, 2)) + ':d=5" -c:a libmp3lame -b:a 128k "' + out + '"'
        try:
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            log_api("music", "Sine", "fallback")
            return True
        except Exception:
            return False


class Background:
    DARK = "eq=contrast=1.06:brightness=0.02:saturation=1.10"
    def __init__(self, base):
        self.base = base
    def get(self, duration, out="bg.mp4"):
        td = duration + 5
        if self._px(td, out):
            return out
        if self._pb(td, out):
            return out
        c0 = "%02x%02x%02x" % (random.randint(10, 30), random.randint(8, 25), random.randint(25, 55))
        c1 = "%02x%02x%02x" % (random.randint(10, 30), random.randint(8, 25), random.randint(25, 55))
        cmd = 'ffmpeg -y -f lavfi -i "gradients=s=1920x1080:c0=0x' + c0 + ':c1=0x' + c1 + ':speed=0.006" -t ' + str(round(td, 2)) + ' -c:v libx264 -preset veryfast -crf 23 ' + out
        self.base.run_cmd(cmd)
        log_api("bg", "Gradient", "fallback")
        return out
    def _px(self, td, out):
        k = os.environ.get("PEXELS_API_KEY")
        if not k:
            return False
        for q in random.sample(["mosque night", "night sky stars", "desert landscape"], 3):
            try:
                url = "https://api.pexels.com/videos/search?query=" + q + "&orientation=landscape&per_page=10"
                r = self.base.session.get(url, headers={"Authorization": k}, timeout=14)
                if r.status_code == 200 and r.json().get("videos"):
                    vs = r.json()["videos"]
                    random.shuffle(vs)
                    for v in vs[:5]:
                        vfs = v.get("video_files", [])
                        if not vfs:
                            continue
                        p = sorted(vfs, key=lambda x: abs(x.get("width", 0) - 1920))[0]
                        if self.base.download(p["link"], "tmp.mp4"):
                            self._r("tmp.mp4", td, out)
                            log_api("bg", "Pexels", "success", q)
                            return True
            except Exception:
                pass
        return False
    def _pb(self, td, out):
        k = os.environ.get("PIXABAY_API_KEY")
        if not k:
            return False
        try:
            url = "https://pixabay.com/api/videos/?key=" + k + "&q=mosque&orientation=horizontal&per_page=10"
            r = self.base.session.get(url, timeout=14)
            if r.status_code == 200 and r.json().get("hits"):
                hs = r.json()["hits"]
                random.shuffle(hs)
                for h in hs[:5]:
                    for sk in ["medium", "small", "large"]:
                        u = h.get("videos", {}).get(sk, {}).get("url")
                        if not u:
                            continue
                        if self.base.download(u, "tmp.mp4"):
                            self._r("tmp.mp4", td, out)
                            log_api("bg", "Pixabay", "success")
                            return True
        except Exception:
            pass
        return False
    def _r(self, src, td, out):
        cmd = 'ffmpeg -y -stream_loop -1 -i ' + src + ' -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,' + self.DARK + '" -t ' + str(round(td, 2)) + ' -an -c:v libx264 -preset veryfast -crf 23 -maxrate 6M -bufsize 12M ' + out
        self.base.run_cmd(cmd)


class Drive:
    def __init__(self, base, folder_var="GDRIVE_LONG_VIDEO_FOLDER_ID", chunk=10):
        self.base = base
        self.folder_var = folder_var
        self.chunk = chunk * 1024 * 1024
    def upload(self, path, prefix="Long", retries=3):
        if not path or not os.path.exists(path):
            return None, None
        for i in range(1, retries + 1):
            try:
                r = self._do(path, prefix)
                if r[0]:
                    return r
            except Exception as e:
                log("Drive err: " + str(e))
            if i < retries:
                time.sleep(3 * i)
        return None, None
    def _do(self, path, prefix):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        c = Credentials(None,
            refresh_token=os.environ.get("GOOGLE_DRIVE_REFRESH_TOKEN"),
            client_id=os.environ.get("GOOGLE_DRIVE_CLIENT_ID"),
            client_secret=os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET"),
            token_uri="https://oauth2.googleapis.com/token")
        s = build("drive", "v3", credentials=c, cache_discovery=False)
        m = {"name": prefix + "_" + str(int(time.time())) + ".mp4"}
        fid = os.environ.get(self.folder_var, "").strip()
        if fid:
            m["parents"] = [fid]
        media = MediaFileUpload(path, mimetype="video/mp4", resumable=True, chunksize=self.chunk)
        req = s.files().create(body=m, media_body=media, fields="id")
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        did = resp.get("id")
        if not did:
            return None, None
        try:
            s.permissions().create(fileId=did, body={"type": "anyone", "role": "reader"}).execute()
        except Exception:
            pass
        log_api("drive", "Drive", "success", did)
        return ("https://drive.google.com/file/d/" + did + "/view",
                "https://drive.google.com/uc?export=download&id=" + did)


class Mastering:
    TEMPO = 0.92
    VOLUME = 1.25
    def __init__(self, base):
        self.base = base
    def master(self, in_f, out_f):
        cmd = 'ffmpeg -y -i "' + in_f + '" -af "atempo=' + str(self.TEMPO) + ',loudnorm=I=-16:TP=-1.5:LRA=11,volume=' + str(self.VOLUME) + '" "' + out_f + '"'
        try:
            subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
            return out_f
        except Exception:
            shutil.copy(in_f, out_f)
            return out_f


class FontManager:
    _F = {"arabic": ["/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"],
          "devanagari": ["/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"],
          "latin": ["/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]}
    _c = {}
    @staticmethod
    def get(size, script="latin"):
        k = (size, script)
        if k in FontManager._c:
            return FontManager._c[k]
        for p in FontManager._F.get(script, FontManager._F["latin"]):
            if os.path.exists(p):
                try:
                    f = ImageFont.truetype(p, size)
                    FontManager._c[k] = f
                    return f
                except Exception:
                    continue
        f = ImageFont.load_default()
        FontManager._c[k] = f
        return f


def wrap_text(draw, text, font, max_w=1700):
    if not text:
        return []
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        t = (cur + " " + w).strip()
        b = draw.textbbox((0, 0), t, font=font)
        if b[2] - b[0] <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_centered(draw, text, y, font, fill, W=1920, shadow=True):
    if not text:
        return
    b = draw.textbbox((0, 0), text, font=font)
    w = b[2] - b[0]
    x = (W - w) // 2
    if shadow:
        draw.text((x + 4, y + 4), text, fill=(0, 0, 0, 220), font=font)
    draw.text((x, y), text, fill=fill, font=font)


def draw_badge(draw, text, y=60):
    if not text:
        return
    W, H = draw.im.size
    f = FontManager.get(32, "latin")
    b = draw.textbbox((0, 0), text, font=f)
    w = b[2] - b[0]
    draw.rounded_rectangle([80, y, 80 + w + 32, y + 50], radius=10,
        fill=(20, 15, 8, 200), outline=(212, 175, 55, 220), width=2)
    draw.text((96, y + 10), text, fill=(230, 200, 130), font=f)


def draw_sparkles(draw, t, count=12):
    W, H = draw.im.size
    rng = random.Random(int(t * 10))
    for _ in range(count):
        x = rng.randint(int(W * 0.08), W - int(W * 0.08))
        y = rng.randint(int(H * 0.10), H - int(H * 0.10))
        s = rng.randint(3, 9)
        a = max(50, min(255, int(120 + 100 * math.sin(t * 3 + x))))
        draw.ellipse([x - s, y - s, x + s, y + s], fill=(255, 240, 180, a))


def draw_progress(draw, current, total, y=None):
    W, H = draw.im.size
    if y is None:
        y = H - 40
    mx = int(W * 0.07)
    bw = W - (mx * 2)
    bh = 8
    draw.rectangle([mx, y, mx + bw, y + bh], fill=(0, 0, 0, 150))
    pct = min(1.0, current / max(total, 1))
    fw = int(bw * pct)
    if fw > 0:
        draw.rectangle([mx, y, mx + fw, y + bh], fill=(212, 175, 55, 255))


def draw_watermark(img, logo, size=(200, 90), pos="top-right", opacity=0.55):
    if not os.path.exists(logo):
        return
    try:
        W, H = img.size
        wm = Image.open(logo).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
        a = wm.split()[3].point(lambda v: int(v * opacity))
        wm.putalpha(a)
        pad = int(W * 0.03)
        if pos == "top-right":
            x, y = W - size[0] - pad, pad
        else:
            x, y = pad, pad
        img.paste(wm, (x, y), wm)
    except Exception:
        pass


class LogoProcessor:
    C = ["logo.png", "assets/logo.png", "../logo.png", "../assets/logo.png", "logo.jpg"]
    def make(self, out="avatar.png"):
        for c in self.C:
            if os.path.exists(c):
                try:
                    img = Image.open(c).convert("RGBA")
                    if img.width > 600:
                        r = 600 / img.width
                        img = img.resize((600, int(img.height * r)), Image.Resampling.LANCZOS)
                    b = 14
                    bot = 30
                    nw = img.width + b * 2
                    nh = img.height + b + bot
                    canvas = Image.new("RGBA", (nw, nh), (0, 0, 0, 0))
                    d = ImageDraw.Draw(canvas)
                    d.rectangle([0, 0, nw - 1, nh - 1], outline=(212, 175, 55, 255), width=b)
                    canvas.paste(img, (b, b), img)
                    canvas.save(out)
                    return True
                except Exception:
                    continue
        return False


def draw_outro(img, draw, t, dur, hl):
    a = min(1.0, t / 0.5)
    C = (230, 200, 130)
    fo = FontManager.get(96, "latin")
    draw_centered(draw, "JazakAllah Khair", 260, fo, (C[0], C[1], C[2], int(255 * a)), 1920)
    draw_sparkles(draw, t)


class Facebook:
    G = "https://graph.facebook.com/v22.0"
    def __init__(self, base=None):
        self.tok = os.environ.get("FACEBOOK_META_TOKEN") or os.environ.get("FACEBOOK_INSTAGRAM_META_TOKEN")
        self.pid = os.environ.get("FACEBOOK_PAGE_ID")
        self.s = requests.Session()
    def upload(self, vp, cap="Hadith"):
        if not self.tok or not self.pid:
            log_api("fb", "FB", "failed", "no creds")
            return False
        if not os.path.exists(vp):
            return False
        try:
            with open(vp, "rb") as f:
                r = self.s.post(self.G + "/" + self.pid + "/videos",
                    data={"access_token": self.tok, "description": cap, "published": "true"},
                    files={"source": f}, timeout=3600).json()
            if r.get("id"):
                log_api("fb", "FB", "success", r["id"])
                return True
            log_api("fb", "FB", "failed", str(r.get("error", {}))[:100])
        except Exception as e:
            log_api("fb", "FB", "failed", str(e)[:100])
        return False


class YouTube:
    def __init__(self, base=None):
        self.cid = os.environ.get("YOUTUBE_CLIENT_ID")
        self.cs = os.environ.get("YOUTUBE_CLIENT_SECRET")
        self.rt = os.environ.get("YOUTUBE_REFRESH_TOKEN")
        self.plid = os.environ.get("DAILY_HADITH_YT_PLAYLIST_ID")
    def upload(self, vp, title="Hadith", desc="", chapters=None):
        if not self.cid or not self.rt:
            log_api("yt", "YT", "failed", "no creds")
            return False
        if not os.path.exists(vp):
            return False
        if chapters:
            desc += "\n\nTimestamps:\n" + "\n".join(chapters)
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            c = Credentials(None, refresh_token=self.rt, client_id=self.cid,
                client_secret=self.cs, token_uri="https://oauth2.googleapis.com/token")
            yt = build("youtube", "v3", credentials=c, cache_discovery=False)
            body = {"snippet": {"title": title[:100], "description": desc,
                                "tags": ["Hadith", "Islam"], "categoryId": "22"},
                    "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
            media = MediaFileUpload(vp, chunksize=5 * 1024 * 1024, resumable=True, mimetype="video/mp4")
            r = yt.videos().insert(part="snippet,status", body=body, media_body=media)
            resp = None
            retry = 0
            while resp is None:
                try:
                    _, resp = r.next_chunk()
                except Exception:
                    retry += 1
                    if retry > 5:
                        raise
                    time.sleep(2 ** retry)
            vid = resp.get("id")
            if vid:
                log_api("yt", "YT", "success", vid)
                if self.plid:
                    try:
                        yt.playlistItems().insert(part="snippet",
                            body={"snippet": {"playlistId": self.plid,
                                "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
                    except Exception:
                        pass
                return True
        except Exception as e:
            log_api("yt", "YT", "failed", str(e)[:100])
        return False
