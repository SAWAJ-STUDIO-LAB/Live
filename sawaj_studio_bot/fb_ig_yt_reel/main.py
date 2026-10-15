import os
import sys
import traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from base import (
    BasePipeline, Hadith, AIProvider, TTS, Music, Background,
    Drive, Mastering, LogoProcessor, Facebook, Instagram, YouTube,
    run_start, send_report, header, log, log_error,
    draw_intro, draw_main, draw_outro
)
from PIL import Image, ImageDraw
from mutagen.mp3 import MP3


class ReelPipeline(BasePipeline):
    def run(self):
        header("REEL VIDEO PIPELINE")
        ai = AIProvider(self)
        tts = TTS(self)
        mu = Music(self)
        bg = Background(self)
        lp = LogoProcessor()
        ms = Mastering(self)
        dr = Drive(self, "GDRIVE_SHORT_VIDEO_FOLDER_ID", 5)

        header("STEP 1: Hadith")
        hd = Hadith(self, 150, 400)
        h = hd.fetch()

        header("STEP 2: Hindi")
        hindi = ai.call("Is English Hadith ka Hindi tarjuma likho:\n\n" + h["english"], task="hindi")
        if not hindi:
            hindi = "Amal ka daromadar niyaton par hai."

        header("STEP 3: Meaning")
        meaning = ai.call("Is Hadith ka 2-3 line Hindi matlab likho:\n\n" + hindi,
                          max_tokens=300, task="meaning")
        if not meaning:
            meaning = "Is hadith me niyat ki ahmiyat batayi gayi hai."

        header("STEP 4: TTS Hadith")
        tts.generate("Hadith Sharif. " + hindi, "s_raw.mp3")
        ms.master("s_raw.mp3", "s_v.mp3")

        header("STEP 5: TTS Meaning")
        tts.generate("Ab iska matlab suniye. " + meaning, "m_raw.mp3")
        ms.master("m_raw.mp3", "m_v.mp3")

        cmd1 = ('ffmpeg -y -i s_v.mp3 -i m_v.mp3 -filter_complex '
                '"[0:a][1:a]concat=n=2:v=0:a=1[out]" -map "[out]" s_full.mp3')
        self.run_cmd(cmd1)
        vd = MP3("s_full.mp3").info.length

        header("STEP 6: Music")
        mu.get(vd + 15, "music.mp3")
        cmd2 = ('ffmpeg -y -i s_full.mp3 -i music.mp3 -filter_complex '
                '"[1:a]volume=0.18[bg];[0:a][bg]amix=inputs=2:duration=first[aout]" '
                '-map "[aout]" -c:a libmp3lame -b:a 192k s_voice.mp3')
        self.run_cmd(cmd2)

        header("STEP 7: Background")
        bgf = bg.get(vd + 4.5)

        header("STEP 8: Logo")
        hl = lp.make("avatar.png")

        header("STEP 9: Frames")
        lbl = "#" + h["number"] + " - " + h["collection"]
        os.makedirs("p_frames", exist_ok=True)
        fps = 25
        intro = 2.0
        outro = 2.0
        total = intro + vd + outro
        n = int(total * fps)
        for fi in range(n):
            t = fi / fps
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            if t < intro:
                draw_intro(img, d, t, intro, hl)
            elif t < intro + vd:
                draw_main(img, d, t - intro, vd, hindi, h.get("arabic", ""), h["english"], lbl, hl)
            else:
                draw_outro(img, d, t - (intro + vd), outro, hl)
            img.save("p_frames/frame_" + str(fi).zfill(5) + ".png")

        header("STEP 10: Compose")
        os.makedirs("output/final", exist_ok=True)
        cmd = ('ffmpeg -y -i ' + bgf + ' -framerate 25 '
               '-i p_frames/frame_%05d.png -i s_voice.mp3 '
               '-filter_complex "[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[outv]" '
               '-map "[outv]" -map 2:a -c:v libx264 -preset veryfast -crf 22 '
               '-maxrate 8M -bufsize 16M -c:a aac -b:a 192k -t ' + str(round(total, 2)) +
               ' -movflags +faststart output/final/Final_Reel.mp4')
        self.run_cmd(cmd)

        header("STEP 11: Drive")
        dl, dd = dr.upload("output/final/Final_Reel.mp4", "Reel")

        header("STEP 12: Social")
        if self.cfg.post_social:
            plats = self.cfg.platforms()
            if "facebook" in plats:
                Facebook().upload("output/final/Final_Reel.mp4", "Hadith: " + hindi + "\n\n" + meaning)
            if "instagram" in plats and dd:
                Instagram().upload_reel("output/final/Final_Reel.mp4", "Hadith: " + hindi + "\n\n" + meaning, dd)
            if "youtube" in plats:
                YouTube().upload("output/final/Final_Reel.mp4",
                    h["collection"] + " #" + h["number"] + " #Shorts",
                    hindi + "\n\n" + meaning)

        header("DONE")
        self.cleanup(["s_raw.mp3", "s_v.mp3", "m_raw.mp3", "m_v.mp3",
                      "s_full.mp3", "s_voice.mp3", "music.mp3",
                      "tmp.mp4", "avatar.png"], "p_frames")


def main():
    run_start("REEL VIDEO RUN")
    try:
        ReelPipeline().run()
    except Exception as e:
        log_error("reel", str(e))
        log("FATAL: " + str(e), "ERROR")
    send_report()


if __name__ == "__main__":
    main()
