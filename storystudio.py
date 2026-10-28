#!/usr/bin/env python3
"""Tiny French Stories Studio: sequence JSON -> 1080x1920 Story slides (JPEG) + Story clip (MP4) + manifest + QC report.

Reuses small.py / sprites.py (Adrien and Marinette, Paris scenes, French edge-tts voices). All French/English text is
drawn from the sequence JSON as live text at render time (never baked into generated art), so edit the JSON and re-render.

  python storystudio.py render [--sequence ID[,ID...]|all] [--dummy-audio] [--no-video]
"""
import argparse, glob, json, os, random, re, shutil, subprocess, sys, tempfile, unicodedata
from PIL import Image, ImageDraw
import small as sm
from small import W, H, FPS, BRAND, font, wrap, card_image, vgrad, make_scene, pill, write_wav
from sprites import sprite, CHARS

ROOT = os.path.dirname(os.path.abspath(__file__))
SEQ_DIR = os.path.join(ROOT, "ig-stories", "sequences")
OUT_DIR = os.path.join(ROOT, "ig-stories", "out")
CFG_PATH = os.path.join(ROOT, "ig-stories", "config.json")
SAFE_TOP, SAFE_BOTTOM = 250, 1580          # Instagram covers the top/bottom of Stories with its own UI
INK, SOFT = (46, 48, 60), (84, 86, 96)
GREEN = (95, 158, 134)                     # Adrien's accent, used for "answer / example" tags
LETTERS = "ABCD"
TYPES = {"intro", "word", "convo", "quiz", "reveal"}
DEFAULT_CFG = {"ig_account": "instagram_shock-latuka", "expect_username": "tiny.french", "handle": "@tiny.french",
               "timezone": "UTC", "cta_default": "More free lessons: link in bio", "voice_rate": "-12%"}


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    if os.path.exists(CFG_PATH):
        cfg.update(json.load(open(CFG_PATH, encoding="utf-8")))
    return cfg


# ---------- drawing helpers ----------
def static_bg(scene):
    """Soft scene-coloured gradient with gentle bokeh circles (no characters, so text cards stay readable)."""
    sc = sm.SCENES.get(scene, sm.SCENES["cafe"])
    img = vgrad(W, H, sc["top"], sc["bot"]).convert("RGBA")
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(over)
    rnd = random.Random(7)
    for _ in range(34):
        r = rnd.randint(30, 110); x = rnd.randint(-30, W + 30); y = rnd.randint(SAFE_TOP - 60, SAFE_BOTTOM + 40)
        d.ellipse((x - r, y - r, x + r, y + r), fill=rnd.choice([(255, 255, 255, 60), (122, 150, 204, 38), (228, 140, 152, 38)]))
    return Image.alpha_composite(img, over).convert("RGB")


def place(img, card, y, warns, what):
    """Paste a card (centered); returns y for the next card and records safe-zone problems."""
    img.paste(card, ((W - card.width) // 2, y), card)
    bottom = y + card.height - 40
    if y + 40 < SAFE_TOP - 10:
        warns.append(f"{what}: starts at y={y + 40}, inside the top UI zone (<{SAFE_TOP})")
    if bottom > SAFE_BOTTOM:
        warns.append(f"{what}: reaches y={bottom}, inside the bottom UI zone (>{SAFE_BOTTOM})")
    return y + card.height - 40 + 10


def lines_parts(text_lines, size, color, adv, bold=True, maxw=840):
    f = font(size, bold)
    return [(t, f, color, adv) for raw in text_lines if raw for t in wrap(raw, f, maxw)]


def footer(img, cfg, y=1505):
    ImageDraw.Draw(img).text((W / 2, y), cfg["handle"], font=font(36), fill=BRAND, anchor="mm")


def fit(text, start, stop, maxw=840, bold=True):
    return next((s for s in range(start, stop, -10) if font(s, bold).getlength(text) <= maxw), stop)


def balanced(text, f, maxw):
    """Wrap into the fewest lines, then even the lines out so the last one is not a lone word."""
    lines = wrap(text, f, maxw)
    if len(lines) < 2:
        return lines
    for width in range(int(maxw * 0.55), maxw + 1, 20):
        trial = wrap(text, f, width)
        if len(trial) == len(lines):
            return trial
    return lines


# ---------- static slide types ----------
def slide_intro(sl, seq, cfg):
    """Adrien and Marinette in the sequence's scene with the question card below them."""
    warns = []
    scene = seq.get("scene", "cafe")
    bg, fg = make_scene(scene, {"title": seq.get("title", ""), "scene": scene})
    img = bg.copy()
    for nm, c in CHARS.items():
        s = sprite(nm, 0, False)
        img.paste(s, (c["x"], sm.CHAR_Y), s)
        p = pill(nm, c["accent"]); img.paste(p, (c["x"] + s.width // 2 - p.width // 2, 322), p)
    img.paste(fg, (0, sm.TABLE_TOP - 55), fg)
    parts = lines_parts(sl["headline"], 68, INK, 88) + [("", None, None, 14)] + lines_parts([sl.get("sub", "")], 40, BRAND, 56, False)
    place(img, card_image(sl.get("kicker", "Today's tiny word"), BRAND, parts, min_h=420), sm.CARD_Y - 40, warns, "intro card")
    footer(img, cfg)
    return img, warns


def slide_word(sl, seq, cfg):
    warns, img = [], static_bg(seq.get("scene", "cafe"))
    size = fit(sl["fr"], 190, 80)
    parts = [(sl["fr"], font(size), INK, int(size * 1.2))]
    if sl.get("pron"):
        parts.append((sl["pron"], font(64, False), BRAND, 90))
    parts.append((sl["en"], font(76), SOFT, 100))
    if sl.get("pos"):
        parts.append((sl["pos"], font(40, False), (130, 134, 150), 60))
    tag = f"Word of the day · {seq.get('level', '')}".rstrip(" ·")
    y = place(img, card_image(tag, BRAND, parts, min_h=560), SAFE_TOP + 20, warns, "word card")
    ex = sl["example"]; ef = font(54)
    parts = [(t, ef, INK, 70) for t in balanced(ex["fr"], ef, 840)] + [("", None, None, 8)]
    if ex.get("pron"):
        parts += lines_parts([ex["pron"]], 40, BRAND, 54, False) + [("", None, None, 8)]
    parts += lines_parts([ex["en"]], 42, SOFT, 56, False)
    place(img, card_image("Example", GREEN, parts, min_h=300), y + 10, warns, "example card")
    footer(img, cfg)
    return img, warns


def slide_quiz(sl, seq, cfg):
    warns, img = [], static_bg(seq.get("scene", "cafe"))
    size = fit(sl["fr"], 170, 80)
    parts = [(sl["fr"], font(size), BRAND, int(size * 1.2))] if sl.get("fr") else []
    parts += lines_parts([sl["question"]], 54, INK, 72) + [("", None, None, 20)]
    parts += [(f"{LETTERS[i]}    {o}", font(54, False), INK, 80) for i, o in enumerate(sl["options"])]
    y = place(img, card_image("Quick quiz", BRAND, parts, min_h=700), SAFE_TOP + 20, warns, "quiz card")
    d = ImageDraw.Draw(img)
    d.text((W / 2, y + 70), "Reply A, B, C or D", font=font(56), fill=BRAND, anchor="mm")
    d.text((W / 2, y + 140), "Answer in the next Story", font=font(42, False), fill=SOFT, anchor="mm")
    footer(img, cfg)
    return img, warns


def slide_reveal(sl, seq, cfg):
    warns, img = [], static_bg(seq.get("scene", "cafe"))
    size = fit(sl["fr"], 160, 80)
    head = f"{sl['answer_label']} · {sl['en'][:1].upper() + sl['en'][1:]}"
    parts = [(head, font(fit(head, 84, 50), True), BRAND, 112), (sl["fr"], font(size), INK, int(size * 1.15))]
    if sl.get("pron"):
        parts.append((sl["pron"], font(52, False), SOFT, 76))
    parts.append(("", None, None, 14))
    parts += lines_parts(sl.get("note", []), 40, SOFT, 56, False)
    y = place(img, card_image("Answer", GREEN, parts, min_h=700), SAFE_TOP + 20, warns, "answer card")
    cta = wrap(sl.get("cta") or cfg["cta_default"], font(40), 900)
    d = ImageDraw.Draw(img)
    for i, t in enumerate(cta):
        d.text((W / 2, y + 60 + i * 56), t, font=font(40), fill=BRAND, anchor="mm")
    if sl.get("teaser"):  # optional, e.g. "Next: merci (thank you)" - gives followers a reason to come back
        ty = y + 60 + len(cta) * 56 + 50
        d.text((W / 2, ty), sl["teaser"], font=font(46), fill=INK, anchor="mm")
        if ty + 30 > SAFE_BOTTOM:
            warns.append(f"teaser line reaches y={ty + 30}, inside the bottom UI zone (>{SAFE_BOTTOM})")
    footer(img, cfg)
    return img, warns


STATIC = {"intro": slide_intro, "word": slide_word, "quiz": slide_quiz, "reveal": slide_reveal}


def save_jpeg(img, path):
    img.convert("RGB").save(path, "JPEG", quality=92, optimize=True, subsampling=0)


# ---------- conversation clip ----------
def render_convo(sl, seq, cfg, out_mp4, poster, dummy):
    """Reuses small.py's characters/scene/voices; no vocab section so the clip stays Story-length."""
    text = f"title: {sl.get('title', 'Tiny chat')}\nscene: {sl.get('scene', seq.get('scene', 'cafe'))}\n\n"
    for ln in sl["lines"]:
        text += f"{ln['speaker']}: {ln['fr']} | {ln['en']}" + (f" | {ln['pron']}" if ln.get("pron") else "") + "\n"
    status = "placeholder_tone" if dummy else "real_voice"
    with tempfile.TemporaryDirectory() as tmp:
        meta, lines, vocab, audio, n, frame = sm.build(text, cfg["voice_rate"], dummy, tmp)
        # small.synth falls back to lower-quality gTTS unless STRICT_VOICE=1 (the workflow sets it), so a fallback is never silent.
        wav = os.path.join(tmp, "final.wav"); write_wav(wav, audio)
        l = lines[min(1, len(lines) - 1)]
        frame(int((l["start"] + 0.5) * FPS)).save(poster, "JPEG", quality=90)
        tmp_mp4 = os.path.join(tmp, "clip.mp4")
        p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "warning", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                              "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-threads", "2", "-crf", "20",
                              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", tmp_mp4],
                             stdin=subprocess.PIPE)
        for i in range(n):
            p.stdin.write(frame(i).tobytes())
        p.stdin.close(); p.wait()
        if p.returncode:
            raise RuntimeError(f"ffmpeg failed (exit {p.returncode})")
        shutil.copyfile(tmp_mp4, out_mp4)
    return {"duration": round(n / FPS, 1), "size_mb": round(os.path.getsize(out_mp4) / 1e6, 2), "audio": status,
            "audio_transcript": [l["fr"] for l in sl["lines"]], "subtitles": [{"fr": l["fr"], "en": l["en"]} for l in sl["lines"]]}


# ---------- QC (consistency checks; NOT a language verification) ----------
def norm(s):
    """Lower-case, accent-free, punctuation-free, apostrophes unified: for comparing French strings."""
    s = unicodedata.normalize("NFD", s.lower().replace("’", "'"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("'", "")
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


def qc(seq, convo_info, layout_warns, known_words, convo_lines):
    errors, warns, checks = [], list(layout_warns), []
    slides = seq["slides"]
    for t in [s.get("type") for s in slides]:
        if t not in TYPES:
            errors.append(f"unknown slide type: {t}")
    word = next((s for s in slides if s.get("type") == "word"), None)
    quiz = next((s for s in slides if s.get("type") == "quiz"), None)
    reveal = next((s for s in slides if s.get("type") == "reveal"), None)

    if word:
        ex = word["example"]
        ok = norm(word["fr"]) in norm(ex["fr"])
        checks.append({"check": "example sentence contains the target word", "ok": ok})
        if not ok:
            warns.append("example sentence does not contain the target word in the same form (check conjugation / agreement)")
        if convo_lines:
            ok = any(norm(word["fr"]) in norm(l["fr"]) for l in convo_lines)
            checks.append({"check": "conversation uses the target word", "ok": ok})
            if not ok:
                warns.append("none of the conversation lines contains the target word in the same form")
        if not word.get("pron"):
            warns.append("word slide has no pronunciation hint ('pron')")
        if not norm(word["fr"]):
            errors.append("word slide: empty French word")
        if word["fr"] in known_words and known_words[word["fr"]] != seq["id"]:
            warns.append(f"duplicate: '{word['fr']}' already used in sequence '{known_words[word['fr']]}'")
    if quiz:
        n = len(quiz["options"])
        ok = isinstance(quiz.get("answer"), int) and 0 <= quiz["answer"] < n and 3 <= n <= 4 and len({o.lower() for o in quiz["options"]}) == n
        checks.append({"check": "quiz has 3-4 unique options and exactly one valid correct answer", "ok": ok})
        if not ok:
            errors.append("quiz options/answer invalid")
        elif word and quiz["options"][quiz["answer"]].lower() != word["en"].lower():
            errors.append(f"quiz correct option '{quiz['options'][quiz['answer']]}' != word meaning '{word['en']}'")
        else:
            checks.append({"check": "quiz correct option equals the taught meaning", "ok": True})
        if quiz.get("fr") and word and quiz["fr"] != word["fr"]:
            errors.append("quiz asks about a different word than the word slide")
    if reveal and quiz and isinstance(quiz.get("answer"), int) and 0 <= quiz["answer"] < len(quiz["options"]):
        ok = reveal["answer_label"] == LETTERS[quiz["answer"]] and reveal["en"].lower() == quiz["options"][quiz["answer"]].lower()
        checks.append({"check": "reveal slide matches the quiz answer", "ok": ok})
        if not ok:
            errors.append("reveal slide does not match the quiz answer")
    if reveal and word:
        ok = reveal["fr"] == word["fr"]
        checks.append({"check": "reveal slide repeats the same word", "ok": ok})
        if not ok:
            errors.append("reveal word differs from word slide")
    if convo_info:
        checks.append({"check": "audio transcript == subtitles (both generated from the same text)",
                       "ok": convo_info["audio_transcript"] == [s["fr"] for s in convo_info["subtitles"]]})
        if convo_info["audio"] != "real_voice":
            errors.append(f"conversation audio is {convo_info['audio']} (placeholder tone), not the natural French voices - re-render")
        if convo_info["duration"] > 60 or convo_info["duration"] < 3:
            errors.append(f"clip duration {convo_info['duration']}s outside Story limits (3-60s)")
        elif convo_info["duration"] > 12:
            warns.append(f"clip is {convo_info['duration']}s (target 5-12s)")
        if convo_info["size_mb"] > 8:
            warns.append(f"clip is {convo_info['size_mb']} MB; some sources report an 8 MB Story video limit")
    for i, s in enumerate(slides, 1):
        for k in ("fr", "en", "question"):
            if k in s and not str(s[k]).strip():
                errors.append(f"slide {i}: empty '{k}'")
    notes = ["Automated checks only prove internal consistency. They cannot prove the French is natural or correct.",
             "Pronunciation hints are approximate English-style respellings and were not machine-checked."]
    approved = bool(seq.get("approved")) and bool(str(seq.get("reviewed_by", "")).strip())
    return {"errors": errors, "warnings": warns, "checks": checks, "uncertain": seq.get("uncertain", []), "notes": notes,
            "french_verified": False,
            "status": "blocked" if errors else ("ready" if approved else "needs_review")}


# ---------- main ----------
def render_sequence(path, cfg, args, known_words):
    seq = json.load(open(path, encoding="utf-8"))
    sid = seq["id"]; out = os.path.join(OUT_DIR, sid); os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "*")):
        os.unlink(f)
    slides_out, layout_warns, convo_info, convo_lines, errors = [], [], None, [], []
    # A slide with "skip": true is not rendered or posted, but still feeds the QC checks (e.g. word + quiz consistency).
    for i, sl in enumerate([x for x in seq["slides"] if not x.get("skip")], 1):
        t = sl["type"]; base = f"{i:02d}-{t}"
        if t == "convo":
            convo_lines = sl["lines"]
            if args.no_video:
                continue
            mp4, poster = os.path.join(out, base + ".mp4"), os.path.join(out, base + "-poster.jpg")
            try:
                convo_info = render_convo(sl, seq, cfg, mp4, poster, args.dummy_audio)
            except sm.ScriptProblem as e:
                errors.append(f"slide {i}: conversation script problem: {e}"); continue
            slides_out.append({"n": i, "type": t, "kind": "video", "file": base + ".mp4", "poster": base + "-poster.jpg", **convo_info})
        elif t in STATIC:
            img, w = STATIC[t](sl, seq, cfg)
            save_jpeg(img, os.path.join(out, base + ".jpg"))
            layout_warns += [f"slide {i}: {x}" for x in w]
            slides_out.append({"n": i, "type": t, "kind": "image", "file": base + ".jpg"})
        else:
            slides_out.append({"n": i, "type": t, "kind": "unknown", "file": ""})
        slides_out[-1]["content"] = {k: v for k, v in sl.items() if k != "type"}
    report = qc(seq, convo_info, layout_warns, known_words, convo_lines)
    report["errors"] = errors + report["errors"]
    if errors:
        report["status"] = "blocked"
    manifest = {
        "id": sid, "title": seq.get("title", sid), "level": seq.get("level", ""), "order": seq.get("order", 0),
        "approved": bool(seq.get("approved")), "reviewed_by": seq.get("reviewed_by", ""), "publish_at": seq.get("publish_at", ""),
        "timezone": cfg["timezone"], "ready_to_publish": report["status"] == "ready", "qc": report, "slides": slides_out,
        "source": f"ig-stories/sequences/{os.path.basename(path)}",
        "api_limits": ["Stories are single-media: each slide is posted as its own Story.",
                       "The Instagram API cannot add stickers (poll, quiz, link, question) or captions to Stories.",
                       "The API has no native scheduling: this project's scheduled workflow publishes at publish_at."],
        "manual_steps": [
            "Optional: post the quiz slide by hand in the Instagram app and add the native Quiz sticker (options from the quiz slide, correct answer set) instead of the text-reply version. Sticker taps are the strongest engagement signal on Stories.",
            "Optional: add a Link sticker to the last Story by hand if you want a tappable link to the free lesson."
        ] if any(s["type"] == "quiz" for s in seq["slides"]) else [],
    }
    json.dump(manifest, open(os.path.join(out, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return manifest


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["render"])
    ap.add_argument("--sequence", default="all", help="sequence id, comma-separated ids, or 'all'")
    ap.add_argument("--dummy-audio", action="store_true", help="TEST ONLY: tones instead of voices (such a sequence is blocked from publishing)")
    ap.add_argument("--no-video", action="store_true")
    args = ap.parse_args(); cfg = load_cfg()
    paths = sorted(glob.glob(os.path.join(SEQ_DIR, "*.json")))
    if args.sequence.strip() not in ("all", ""):
        want = {x.strip() for x in args.sequence.split(",") if x.strip()}
        have = {os.path.basename(p)[:-5] for p in paths}
        if want - have:
            sys.exit(f"No such sequence: {', '.join(sorted(want - have))}")
        paths = [p for p in paths if os.path.basename(p)[:-5] in want]
    known = {}
    for p in sorted(glob.glob(os.path.join(SEQ_DIR, "*.json"))):
        s = json.load(open(p, encoding="utf-8"))
        for sl in s["slides"]:
            if sl.get("type") == "word":
                known.setdefault(sl["fr"], s["id"])
    os.makedirs(OUT_DIR, exist_ok=True)
    failed = 0
    for p in paths:
        m = render_sequence(p, cfg, args, known)
        print(f"{m['id']}: status={m['qc']['status']} errors={len(m['qc']['errors'])} warnings={len(m['qc']['warnings'])}")
        for e in m["qc"]["errors"]:
            print("  ERROR:", e)
        for w in m["qc"]["warnings"]:
            print("  warn:", w)
        failed += bool(m["qc"]["errors"])
    index = []
    for mp in sorted(glob.glob(os.path.join(OUT_DIR, "*", "manifest.json"))):
        m = json.load(open(mp, encoding="utf-8"))
        index.append({k: m.get(k, "") for k in ("id", "title", "level", "order", "approved", "ready_to_publish", "publish_at")} | {"status": m["qc"]["status"]})
    index.sort(key=lambda x: (x["order"] or 0, x["id"]))
    json.dump(index, open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    if failed:
        print(f"::warning::{failed} sequence(s) have QC errors and will not be published until fixed")


if __name__ == "__main__":
    main()
