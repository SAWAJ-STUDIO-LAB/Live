import os
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from base import (
    BasePipeline, Hadith, AIProvider, TTS, Music, Background,
    Drive, Mastering, LogoProcessor, Facebook, YouTube,
    FontManager, wrap_text, draw_centered, draw_badge,
    draw_sparkles, draw_progress, draw_watermark, draw_outro,
    run_start, send_report, header, log, log_error
)
from PIL import Image, ImageDraw
from mutagen.mp3 import MP3


def l_ar(draw, s, e, a, W):
    text = s.get("text", "")
    if not text:
        return
    f = FontManager.get(88, "arabic")
    ls = wrap_text(draw, text, f, 1700)
    d = max(s.get("dur", 60), 1)
    p = min(1.0, e / d)
    si = int(p * max(0, len(ls) - 5))
    y = 350
    for line in ls[si:si + 5]:
        bb = draw.textbbox((0, 0), line, font=f)
        w = bb[2] - bb[0]
        x = (W - w) // 2
        draw.text((x, y), line, fill=(240, 210, 150, int(255 * a)), font=f)
        y += 110


def l_hi(draw, s, e, a, W):
    text = s.get("text", "")
    if not text:
        return
    f = FontManager.get(64, "devanagari")
    d = max(s.get("dur", 90), 1)
    p = min(1.0, e / d)
    w = text.split()
    sh = max(1, int(p * len(w)))
    v = " ".join(w[:sh])
    ls = wrap_text(draw, v, f, 1700)[-7:]
    y = 320
    for line in ls:
        bb = draw.textbbox((0, 0), line, font=f)
        ww = bb[2] - bb[0]
        x = (W - ww) // 2
        draw.text((x, y), line, fill=(255, 245, 220, int(255 * a)), font=f)
        y += 85


def l_tash(draw, s, e, a, W):
    text = s.get("text", "")
    if not text:
        return
    f = FontManager.get(42, "devanagari")
    ls = wrap_text(draw, text, f, 1700)
    d = max(s.get("dur", 300), 1)
    p = min(1.0, e / d)
    si = int(p * max(0, len(ls) - 12))
    y = 240
    for line in ls[si:si + 12]:
        bb = draw.textbbox((0, 0), line, font=f)
        ww = bb[2] - bb[0]
        x = (W - ww) // 2
        draw.text((x, y), line, fill=(235, 230, 215, int(255 * a)), font=f)
        y += 58


def l_bu(draw, s, e, a, W):
    data = s.get("data", {})
    hi = data.get("hindi", [])
    ar = data.get("arabic", [])
    en = data.get("english", [])
    fh = FontManager.get(42, "devanagari")
    fa = FontManager.get(42, "arabic")
    fe = FontManager.get(42, "latin")
    du = max(s.get("dur", 90), 1)
    p = min(1.0, e / du)
    y = 200
    gap = 82
    for i, it in enumerate(hi[:3]):
        c = (240, 130, 200, int(255 * a)) if p * 3 >= i else (100, 80, 100, int(180 * a))
        bb = draw.textbbox((0, 0), it, font=fh)
        w = bb[2] - bb[0]
        draw.text(((W - w) // 2, y), it, fill=c, font=fh)
        y += gap
    y += 24
    for i, it in enumerate(ar[:3]):
        c = (90, 170, 255, int(255 * a)) if p * 3 >= i else (60, 90, 130, int(180 * a))
        bb = draw.textbbox((0, 0), it, font=fa)
        w = bb[2] - bb[0]
        draw.text(((W - w) // 2, y), it, fill=c, font=fa)
        y += gap
    y += 24
    for i, it in enumerate(en[:3]):
        c = (255, 110, 110, int(255 * a)) if p * 3 >= i else (130, 70, 70, int(180 * a))
        bb = draw.textbbox((0, 0), it, font=fe)
        w = bb[2] - bb[0]
        draw.text(((W - w) // 2, y), it, fill=c, font=fe)
        y += gap


class LongPipeline(BasePipeline):
    def run(self):
        header("LONG VIDEO PIPELINE")
        ai = AIProvider(self)
        tts = TTS(self)
        mu = Music(self)
        bg = Background(self)
        lp = LogoProcessor()
        ms = Mastering(self)
        dr = Drive(self, "GDRIVE_LONG_VIDEO_FOLDER_ID", 10)

        header("STEP 1: Hadith")
        hd = Hadith(self, 400, 1800)
        h = hd.fetch()
        book = h.get("book", h.get("collection", "Sahih Bukhari"))
        hn = h.get("hadith_no", h.get("number", "1"))

        header("STEP 2: Hindi")
        hindi = ai.call("Is English Hadith ka Hindi tarjuma likho:\n\n" + h["english"], task="hindi")
        if not hindi:
            hindi = "Amal ka daromadar niyaton par hai."

        header("STEP 3: Tashreeh")
        tash = ai.call("Is Hadith ka detailed Hindi Tashreeh likho (250-500 words):\n\n" + hindi,
                       max_tokens=1500, task="tashreeh")
        if not tash:
            tash = "Is hadith me niyat ki ahmiyat batayi gayi hai."

        header("STEP 4: Bullets")
        bl_raw = ai.call("3 Hindi lessons and 3 English lessons:\nHINDI:\n- a\n- b\n- c\n\nENGLISH:\n- a\n- b\n- c\n\nHadith:\n" + hindi,
                         max_tokens=500, task="bullets")
        hi_l = []
        en_l = []
        mode = None
        for ln in (bl_raw or "").split("\n"):
            line = ln.strip()
            if "HINDI" in line.upper():
                mode = "hi"
                continue
            if "ENGLISH" in line.upper():
                mode = "en"
                continue
            if line.startswith("-"):
                it = line.lstrip("-").strip()
                if mode == "hi":
                    hi_l.append(it)
                elif mode == "en":
                    en_l.append(it)
        if not hi_l:
            hi_l = ["Niyat sabse ahem hai.", "Amal ka badla niyat par hai.", "Allah dil janta hai."]
        if not en_l:
            en_l = ["Purity of intention is paramount.", "Rewards depend on intent.", "Allah knows hearts."]
        ar_src = h.get("arabic", "")
        ar_l = [p.strip()[:60] for p in ar_src.split("،") if p.strip()][:3]
        if not ar_l:
            ar_l = ["Innamal aamalu bin niyyat"]
        while len(ar_l) < 3:
            ar_l.append(ar_l[-1])
        bullets = {"hindi": hi_l[:3], "arabic": ar_l[:3], "english": en_l[:3]}

        header("STEP 5: TTS Hadith")
        tts.generate("Hadith Sharif. " + hindi, "l_h_raw.mp3")
        ms.master("l_h_raw.mp3", "l_h.mp3")
        dh = MP3("l_h.mp3").info.length

        header("STEP 6: TTS Tashreeh")
        tts.generate("Ab tafseel suniye. " + tash, "l_t_raw.mp3")
        ms.master("l_t_raw.mp3", "l_t.mp3")
        dt = MP3("l_t.mp3").info.length

        header("STEP 7: TTS Bullets")
        bh = " ".join(bullets["hindi"]) + "."
        tts.generate("Sabaq. " + bh, "l_b_raw.mp3")
        ms.master("l_b_raw.mp3", "l_b.mp3")
        db = MP3("l_b.mp3").info.length

        header("STEP 8: Concat")
        cmd1 = ('ffmpeg -y -i l_h.mp3 -i l_t.mp3 -i l_b.mp3 -filter_complex '
                '"[0:a][1:a][2:a]concat=n=3:v=0:a=1[out]" -map "[out]" l_full.mp3')
        self.run_cmd(cmd1)
        vd = MP3("l_full.mp3").info.length

        header("STEP 9: Music")
        mu.get(vd + 20, "music.mp3")
        cmd2 = ('ffmpeg -y -i l_full.mp3 -i music.mp3 -filter_complex '
                '"[1:a]volume=0.18[bg];[0:a][bg]amix=inputs=2:duration=first[aout]" '
                '-map "[aout]" -c:a libmp3lame -b:a 192k l_voice.mp3')
        self.run_cmd(cmd2)

        header("STEP 10: Background")
        bgf = bg.get(vd + 6.5)

        header("STEP 11: Logo")
        hl = lp.make("avatar.png")

        header("STEP 12: Frames")
        lbl = "#" + hn + " - " + book
        sections = [
            {"type": "arabic", "text": h.get("arabic", ""), "dur": dh * 0.4},
            {"type": "hindi", "text": hindi, "dur": dh * 0.6},
            {"type": "tashreeh", "text": tash, "dur": dt},
            {"type": "bullets", "data": bullets, "dur": db},
        ]
        os.makedirs("l_frames", exist_ok=True)
        fps = 25
        intro = 3.0
        outro = 3.0
        total = intro + vd + outro
        n = int(total * fps)

        def _find(mt):
            acc = 0.0
            for s in sections:
                d = s.get("dur", 0)
                if mt < acc + d:
                    return s, mt - acc
                acc += d
            return None, 0

        for fi in range(n):
            t = fi / fps
            img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            if t < intro:
                p = t / intro
                a = min(1.0, t / 0.5)
                fa = FontManager.get(72, "arabic")
                ft = FontManager.get(110, "latin")
                C = (230, 200, 130)
                b = "Bismillah"
                bb = d.textbbox((0, 0), b, font=fa)
                w = bb[2] - bb[0]
                x = (1920 - w) // 2
                d.text((x, 120), b, fill=(C[0], C[1], C[2], int(255 * a)), font=fa)
                tp = min(1.0, max(0.0, (p - 0.5) / 0.4))
                if tp > 0:
                    draw_centered(d, "HADITH OF THE DAY", 720, ft, (C[0], C[1], C[2], int(255 * tp)), 1920)
                draw_sparkles(d, t)
            elif t < intro + vd:
                mt = t - intro
                a = min(1.0, mt / 0.5)
                if lbl:
                    draw_badge(d, lbl, 60)
                if hl:
                    draw_watermark(img, "avatar.png", (200, 90), "top-right", 0.55)
                cur, se = _find(mt)
                if cur:
                    ty = cur.get("type", "")
                    if ty == "arabic":
                        l_ar(d, cur, se, a, 1920)
                    elif ty == "hindi":
                        l_hi(d, cur, se, a, 1920)
                    elif ty == "tashreeh":
                        l_tash(d, cur, se, a, 1920)
                    elif ty == "bullets":
                        l_bu(d, cur, se, a, 1920)
                draw_progress(d, mt, vd)
                draw_sparkles(d, mt)
            else:
                draw_outro(img, d, t - (intro + vd), outro, hl)
            img.save("l_frames/frame_" + str(fi).zfill(5) + ".png")

        header("STEP 13: Compose")
        os.makedirs("output/final", exist_ok=True)
        cmd = ('ffmpeg -y -i ' + bgf + ' -framerate 25 '
               '-i l_frames/frame_%05d.png -i l_voice.mp3 '
               '-filter_complex "[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[outv]" '
               '-map "[outv]" -map 2:a -c:v libx264 -preset veryfast -crf 22 '
               '-c:a aac -b:a 192k -t ' + str(round(total, 2)) +
               ' -movflags +faststart output/final/Final_Long.mp4')
        self.run_cmd(cmd)

        header("STEP 14: Drive")
        dr.upload("output/final/Final_Long.mp4", "Long")

        header("STEP 15: Social")
        if self.cfg.post_social:
            plats = self.cfg.platforms()
            if "facebook" in plats:
                Facebook().upload("output/final/Final_Long.mp4", "Hadith: " + hindi + "\n\n" + tash)
            if "youtube" in plats:
                YouTube().upload("output/final/Final_Long.mp4",
                    book + " #" + hn,
                    hindi + "\n\n" + tash)

        header("DONE")
        self.cleanup(["l_h_raw.mp3", "l_h.mp3", "l_t_raw.mp3", "l_t.mp3",
                      "l_b_raw.mp3", "l_b.mp3", "l_full.mp3", "l_voice.mp3",
                      "music.mp3", "tmp.mp4", "avatar.png"], "l_frames")


def main():
    run_start("LONG VIDEO RUN")
    try:
        LongPipeline().run()
    except Exception as e:
        log_error("long", str(e))
        log("FATAL: " + str(e), "ERROR")
    send_report()


if __name__ == "__main__":
    main()
