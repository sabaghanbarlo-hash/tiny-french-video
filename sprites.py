"""Drawn characters for Tiny French: Adrien and Marinette (chibi, soft flat colours), animated by code."""
import functools, math
from PIL import Image, ImageDraw, ImageFilter

CHAR_SCALE = 0.9
SKIN = (253, 227, 203)
SKIN_SH = (240, 205, 178)
INK = (92, 52, 56)
CHARS = {
    "Adrien": dict(voice="fr-FR-HenriNeural", accent=(95, 158, 134), x=16),
    "Marinette": dict(voice="fr-FR-DeniseNeural", accent=(228, 140, 152), x=1080 - 16 - int(560 * CHAR_SCALE)),
}


def _bez(p0, p1, p2, n=14):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / n for i in range(n + 1)]]


def lock_pts(root, ctrl, tip, width, n=14):
    """Pointed hair lock along a curve: thick in the middle, sharp at the tip."""
    c = _bez(root, ctrl, tip, n)
    left, right = [], []
    for i, (x, y) in enumerate(c):
        a = c[min(i + 1, n)]; b = c[max(i - 1, 0)]
        dx, dy = a[0] - b[0], a[1] - b[1]; L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        w = width * math.sin(math.pi * (0.12 + 0.88 * i / n) ** 0.9) * (1 - 0.15 * i / n) / 2
        if i == n:
            w = 0
        left.append((x + nx * w, y + ny * w)); right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


def _eyes(d, P, S, blink, lash):
    for ex in (214, 346):
        if blink:
            d.arc(P(ex - 30, 346, ex + 30, 392), 200, 340, fill=(60, 34, 46), width=int(7 * S))
            if lash:
                side = -1 if ex < 280 else 1
                d.line(P(ex + side * 30, 372, ex + side * 42, 362), fill=(52, 28, 40), width=int(5 * S))
            continue
        d.ellipse(P(ex - 27, 318, ex + 27, 396), fill=(58, 30, 46))
        d.ellipse(P(ex - 20, 368, ex + 20, 394), fill=(108, 56, 70))
        d.ellipse(P(ex - 17, 328, ex + 4, 354), fill=(255, 255, 255))
        d.ellipse(P(ex + 6, 368, ex + 17, 380), fill=(255, 255, 255))
        d.arc(P(ex - 31, 312, ex + 31, 378), 195, 345, fill=(52, 28, 40), width=int(7 * S))
        if lash:
            side = -1 if ex < 280 else 1
            d.line(P(ex + side * 28, 344, ex + side * 44, 330), fill=(52, 28, 40), width=int(5 * S))


def _mouth(d, P, S, mouth):
    if mouth == 0:
        d.arc(P(262, 410, 298, 436), 15, 165, fill=INK, width=int(5 * S))
    elif mouth == 1:
        d.ellipse(P(268, 414, 292, 438), fill=(128, 48, 62))
    else:
        d.ellipse(P(260, 410, 300, 446), fill=(128, 48, 62)); d.ellipse(P(268, 430, 292, 444), fill=(238, 128, 140))


def _smooth(layer, S, r=5, thr=120):
    a = layer.getchannel("A").filter(ImageFilter.GaussianBlur(r * S)).point(lambda v: 255 if v > thr else 0)
    layer.putalpha(a.filter(ImageFilter.GaussianBlur(0.8 * S)))
    return layer


@functools.lru_cache(None)
def sprite(name, mouth, blink):
    S = 2 * CHAR_SCALE
    w, h = int(560 * S), int(760 * S)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    P = lambda *v: [int(x * S) for x in v]
    PP = lambda pts: [(x * S, y * S) for x, y in pts]
    ell = lambda box, fill, dd=None: (dd or d).ellipse(P(*box), fill=fill)
    poly = lambda pts, fill, dd=None: (dd or d).polygon(PP(pts), fill=fill)

    def layer(draw_fn, color, r=5):
        L = Image.new("RGBA", (w, h), color + (0,)); dd = ImageDraw.Draw(L); draw_fn(dd)
        L = Image.composite(Image.new("RGBA", (w, h), color + (255,)), L, L.getchannel("A"))
        return _smooth(L, S, r)

    def put(L):
        nonlocal im, d
        im = Image.alpha_composite(im, L); d = ImageDraw.Draw(im)

    def line(pts, col, width):
        d.line(PP(pts), fill=col, width=int(width * S), joint="curve")

    if name == "Adrien":
        gold, gold_d, gold_l = (247, 208, 120), (226, 170, 84), (255, 238, 176)
        # hair behind the head
        def back(dd):
            ell((112, 112, 448, 440), gold, dd)
            for pts in (lock_pts((150, 250), (100, 300), (74, 372), 70), lock_pts((410, 250), (462, 290), (486, 352), 64),
                        lock_pts((262, 124), (288, 76), (338, 58), 54)):
                poly(pts, gold, dd)
        put(layer(back, gold, 4))
        # body: white open jacket, black tee with rainbow stripes
        def jacket(dd):
            poly([(112, 600), (124, 540), (160, 494), (226, 466), (334, 466), (400, 494), (436, 540), (448, 600), (452, 760), (108, 760)], (244, 238, 238), dd)
        put(layer(jacket, (244, 238, 238), 6))
        tee = [(226, 490), (334, 490), (350, 760), (210, 760)]
        poly(tee, (42, 36, 42))
        xl = lambda y: 226 - 16 * (y - 490) / 270; xr = lambda y: 334 + 16 * (y - 490) / 270
        for i, c in enumerate(((110, 176, 120), (150, 108, 190), (244, 202, 100))):
            y0 = 640 + i * 26; y1 = y0 + 18
            poly([(xl(y0), y0), (xr(y0), y0), (xr(y1), y1), (xl(y1), y1)], c)
        poly([(240, 462), (320, 462), (280, 548)], SKIN)                                   # chest V
        poly([(240, 462), (262, 470), (252, 500)], SKIN_SH)
        poly([(214, 472), (246, 462), (238, 548), (198, 520)], (232, 224, 226)); poly([(346, 472), (314, 462), (322, 548), (362, 520)], (232, 224, 226))   # collar
        line([(176, 540), (196, 640)], (226, 216, 218), 4); line([(384, 540), (364, 640)], (226, 216, 218), 4)
        ell((130, 316, 180, 396), SKIN)                                                    # left ear
        ell((136, 154, 424, 462), SKIN)                                                    # face
        # fringe: big swoop from his right to his left
        def front(dd):
            poly([(118, 262), (124, 190), (196, 126), (330, 116), (432, 184), (442, 262), (430, 226), (300, 214), (180, 226)], gold, dd)
            for root, ctrl, tip, wd in (((400, 150), (420, 215), (392, 262), 66), ((340, 140), (330, 225), (296, 276), 70),
                                        ((276, 132), (240, 215), (206, 282), 76), ((206, 140), (166, 220), (150, 310), 74),
                                        ((140, 190), (118, 240), (124, 300), 50)):
                poly(lock_pts(root, ctrl, tip, wd), gold, dd)
        put(layer(front, gold, 2))
        for root, ctrl, tip in (((390, 150), (360, 200), (330, 232)), ((300, 140), (250, 190), (214, 236)), ((236, 132), (196, 180), (168, 232)), ((330, 120), (400, 150), (428, 214))):
            line(_bez(root, ctrl, tip, 10), gold_d, 6)
        for root, ctrl, tip in (((340, 130), (300, 150), (268, 178)), ((240, 126), (212, 146), (196, 176))):
            line(_bez(root, ctrl, tip, 8), gold_l, 5)
        d.arc(P(178, 296, 244, 324), 200, 340, fill=(206, 154, 88), width=int(5 * S)); d.arc(P(316, 290, 382, 318), 200, 340, fill=(206, 154, 88), width=int(5 * S))
        _eyes(d, P, S, blink, lash=False)
    else:
        navy, navy_d, navy_l = (50, 68, 122), (34, 46, 92), (92, 112, 170)
        def back(dd):
            ell((106, 106, 454, 440), navy, dd)
            poly(lock_pts((130, 250), (112, 360), (140, 470), 80), navy, dd); poly(lock_pts((430, 250), (448, 360), (420, 470), 80), navy, dd)
        put(layer(back, navy, 5))
        # body: charcoal jacket over white floral top
        def jacket(dd):
            poly([(150, 610), (160, 548), (186, 498), (240, 466), (320, 466), (374, 498), (400, 548), (410, 610), (414, 760), (146, 760)], (84, 74, 80), dd)
        put(layer(jacket, (84, 74, 80), 6))
        poly([(236, 474), (324, 474), (338, 760), (222, 760)], (242, 234, 234))
        ell((246, 446, 314, 520), SKIN)                                                    # neck / scoop neckline
        poly([(244, 462), (316, 462), (306, 500), (254, 500)], SKIN)
        poly([(226, 468), (252, 466), (264, 560), (240, 640), (212, 540)], (62, 54, 60)); poly([(334, 468), (308, 466), (296, 560), (320, 640), (348, 540)], (62, 54, 60))
        d.arc(P(244, 480, 316, 560), 20, 160, fill=(120, 110, 114), width=int(3 * S))
        for fx, fy in ((262, 640), (296, 660), (270, 690)):
            for ang in range(5):
                ax, ay = fx + 10 * math.cos(ang * 1.2566), fy + 10 * math.sin(ang * 1.2566)
                ell((ax - 7, ay - 7, ax + 7, ay + 7), (238, 150, 170))
            ell((fx - 4, fy - 4, fx + 4, fy + 4), (252, 220, 120))
        for lx, ly, rot in ((244, 668, 1), (300, 636, -1)):
            poly([(lx, ly), (lx + 16 * rot, ly - 8), (lx + 22 * rot, ly + 6)], (66, 80, 74))
        ell((136, 154, 424, 462), SKIN)
        # bangs: swept locks with a parting
        def front(dd):
            poly([(112, 270), (118, 196), (196, 124), (330, 114), (436, 186), (448, 270), (430, 250), (300, 240), (170, 255)], navy, dd)
            for root, ctrl, tip, wd in (((178, 134), (140, 240), (180, 346), 84), ((262, 126), (220, 210), (222, 300), 84),
                                        ((330, 126), (372, 200), (338, 292), 84), ((404, 140), (434, 220), (404, 300), 60)):
                poly(lock_pts(root, ctrl, tip, wd), navy, dd)
        put(layer(front, navy, 2))
        # pigtails with small red ties
        def tails(dd):
            ell((80, 470, 206, 650), navy, dd); ell((354, 470, 480, 650), navy, dd)
            poly(lock_pts((160, 440), (150, 470), (136, 520), 54), navy, dd); poly(lock_pts((400, 440), (410, 470), (424, 520), 54), navy, dd)
        put(layer(tails, navy, 6))
        ell((146, 456, 170, 486), (206, 54, 64)); ell((390, 456, 414, 486), (206, 54, 64))
        for root, ctrl, tip in (((170, 140), (130, 220), (168, 320)), ((260, 130), (222, 180), (232, 250)), ((406, 150), (432, 220), (404, 290))):
            line(_bez(root, ctrl, tip, 10), navy_l, 6)
        line(_bez((110, 520), (100, 570), (130, 620), 10), navy_l, 5); line(_bez((450, 520), (460, 570), (430, 620), 10), navy_l, 5)
        d.arc(P(178, 298, 244, 326), 200, 340, fill=navy_d, width=int(5 * S)); d.arc(P(316, 298, 382, 326), 200, 340, fill=navy_d, width=int(5 * S))
        _eyes(d, P, S, blink, lash=True)
    ell((166, 398, 210, 422), (252, 190, 190)); ell((350, 398, 394, 422), (252, 190, 190))   # small blush
    _mouth(d, P, S, mouth)
    return im.resize((int(560 * CHAR_SCALE), int(760 * CHAR_SCALE)), Image.LANCZOS)
