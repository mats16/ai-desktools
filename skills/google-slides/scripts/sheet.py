# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""usage: uv run -q sheet.py <出力.webp> <画像 ...> [--cols 2] [--width 800] [--per 16]   （--selftest で自己確認）
       uv run -q sheet.py --webp <画像.png ...>   PNG を劣化なしの WebP（同じ名前の .webp）にし、PNG を消す（gslides.py check が取ったページの画像に使う）
スライドの画像を何枚か 1 枚に並べる（まとめて見て確かめるとき）。素の python3 には Pillow がないので uv で動かす。
出力は拡張子の形式で書く。.webp は品質 80（PNG の 5 分の 1 ほど。85 と比べて、モデルが読める文字は変わらなかった。2026-11-02）。長い辺が MAX_EDGE を超える一覧は、MAX_EDGE に縮める。
各ページの上に、ファイル名の番号（p-03.png なら p3）を入れる（見る人が格子の位置を数え間違えないように。ページに重ねない）。
--per を付けると、その枚数ごとに <出力>-1.webp、<出力>-2.webp … に分ける（全体のレビューの一覧は 4 列 × 400 px、16 枚ずつ。deck-review の SKILL.md）。
切り取りは sips でできる（deck-workflow の reuse.md の段階 2）ので、ここには入れていない。"""
import os, re, sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # python3 で回すと、ここで落ちて 1 枚ずつ画像を開くほうへ流れていた（2026-10-16）
    sys.exit("Pillow がない。uv run -q sheet.py … で回す（頭の # /// script が Pillow を入れる）")

MAX_EDGE = 2000  # 一覧の長い辺の上限（px）。pi の read はこれより大きい画像を縮めて送り、Claude も長い辺 2576 px・3.75 MP より大きければ縮める。大きくしても読めるものは増えず、会話に積もるバイトだけが増える（2026-11-02 に、積もった画像でリクエストが 32 MB を超えた）
LABEL = (204, 43, 23)  # 赤の文字の色（deck-design → slides §1 の RED_TEXT）。濃紺の地でも Oat の地でも目立つ


def label(path):
    m = re.search(r"(\d+)\D*$", os.path.basename(path))
    return f"p{int(m.group(1))}" if m else os.path.splitext(os.path.basename(path))[0]


def sheet(paths, cols=2, width=800, gap=8):
    ims = [Image.open(p).convert("RGB") for p in paths]
    ims = [im.resize((width, round(im.height * width / im.width))) for im in ims]
    size = max(14, width // 25)
    head = size + 6  # 番号の帯
    h, rows = max(im.height for im in ims) + head, -(-len(ims) // cols)
    out = Image.new("RGB", (cols * width + (cols - 1) * gap, rows * h + (rows - 1) * gap), "white")
    draw, font = ImageDraw.Draw(out), ImageFont.load_default(size=size)
    for i, (p, im) in enumerate(zip(paths, ims)):
        x, y = (i % cols) * (width + gap), (i // cols) * (h + gap)
        draw.text((x, y + 2), label(p), fill=LABEL, font=font)
        out.paste(im, (x, y + head))
    out.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)  # 縦横の比はそのまま。上限より小さければ何もしない
    return out


def to_webp(paths):
    """PNG を、同じ画素の WebP（劣化なし。Google が描いたページの PNG の 4 割ほど）に置き換える。画素で測るもの（box_pad.py）の結果は変わらない。
    いったん <名前>.webp.tmp に書き、全部書けてから置き換える。書く途中で止まれば、1 枚も置き換えず、前からあるファイルにも触れない。
    置き換える途中で止まれば、置き換えた WebP も消す（PNG はどれも残っているので、何もなくならない）。.tmp も残さない。"""
    made, replaced = [], []
    try:
        for p in paths:
            if (out := os.path.splitext(p)[0] + ".webp") == p:  # もう WebP。消すと、ただ 1 つの画像がなくなる
                continue
            made.append((p, out))
            with Image.open(p) as im:  # 消す前に閉じる（Windows は開いたファイルを消せない）
                im.save(out + ".tmp", "WEBP", lossless=True)
        for _, out in made:
            os.replace(out + ".tmp", out)
            replaced.append(out)
    except BaseException:
        for f in [out + ".tmp" for _, out in made] + replaced:  # 書きかけの 1 枚も、置き換えた WebP も消す（書く途中で止まれば、前からある WebP には触れない）
            if os.path.exists(f):
                os.remove(f)
        raise
    for p, _ in made:
        os.remove(p)


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for i, c in enumerate(("red", "green", "blue")):
            paths.append(os.path.join(d, f"p-{i + 1:02d}.png"))
            Image.new("RGB", (1600, 900), c).save(paths[-1])
        out = sheet(paths, cols=2, width=400)
        big = sheet(paths, cols=3, width=800)  # 3 列 × 800 px（2416 px）は上限まで縮める
        assert max(big.size) == MAX_EDGE and abs(big.size[1] - 488 * MAX_EDGE / 2416) <= 1  # 1 段 488 px（番号の帯 38 px）。縦横の比はそのまま
        im = Image.new("RGB", (1600, 900), "white")
        im.paste((12, 34, 56), (100, 100, 300, 120))
        im.save(f := os.path.join(d, "p-09.png"))
        to_webp([f])
        assert not os.path.exists(f) and Image.open(f[:-4] + ".webp").convert("RGB").tobytes() == im.tobytes()  # 画素は同じ
        to_webp([f[:-4] + ".webp"])
        assert os.path.exists(f[:-4] + ".webp")  # WebP を渡しても消さない
        im.save(good := os.path.join(d, "p-10.png"))
        open(bad := os.path.join(d, "p-11.png"), "wb").write(b"not a png")
        try:
            to_webp([good, bad])
            raise AssertionError("壊れた PNG で止まらなかった")
        except OSError:
            pass
        assert os.path.exists(good) and os.path.exists(bad) and not os.path.exists(good[:-4] + ".webp")  # 1 枚も置き換えない
        im.save(bad[:-4] + ".webp", lossless=True)  # 前からある WebP は、途中で止まっても残す
        try:
            to_webp([good, bad])
        except OSError:
            pass
        assert os.path.exists(bad[:-4] + ".webp") and not [f for f in os.listdir(d) if f.endswith(".tmp")]
        os.remove(bad)
        im.save(bad)
        real, calls = os.replace, []
        os.replace = lambda a, b: calls.append(a) or (real(a, b) if len(calls) < 2 else (_ for _ in ()).throw(OSError("置き換えで止まった")))
        try:
            to_webp([good, bad])
            raise AssertionError("置き換えで止まらなかった")
        except OSError:
            pass
        finally:
            os.replace = real
        assert os.path.exists(good) and os.path.exists(bad) and not os.path.exists(good[:-4] + ".webp") and not [f for f in os.listdir(d) if f.endswith(".tmp")]  # PNG は消さず、置き換えた WebP も .tmp も残さない
    assert out.size == (808, 502)  # 2 列・2 段、間は 8 px、各段の上に 22 px の番号の帯（幅 400 なら文字は 16 px）
    assert out.getpixel((0, 22)) == (255, 0, 0) and out.getpixel((408, 22)) == (0, 128, 0) and out.getpixel((0, 277)) == (0, 0, 255)
    assert out.getpixel((807, 501)) == (255, 255, 255)  # 足りないところは白
    assert LABEL in {c for _, c in out.crop((0, 0, 80, 22)).getcolors(10000)}  # ページの上の帯に番号
    assert label("/tmp/x/p-03.png") == "p3" and label("a.png") == "a"
    print("selftest ok")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["--selftest"]:
        sys.exit(selftest())
    if a[:1] == ["--webp"]:
        sys.exit(to_webp(a[1:]))
    opt = {"--cols": 2, "--width": 800, "--per": 0}
    for k in opt:
        if k in a:
            i = a.index(k)
            opt[k] = int(a[i + 1])
            del a[i:i + 2]
    if len(a) < 2:
        sys.exit(__doc__)
    out, paths = a[0], a[1:]
    per = opt["--per"] or len(paths)
    chunks = [paths[k:k + per] for k in range(0, len(paths), per)]
    stem, ext = os.path.splitext(out)
    for n, ch in enumerate(chunks, 1):
        name = out if len(chunks) == 1 else f"{stem}-{n}{ext}"
        sheet(ch, opt["--cols"], opt["--width"]).save(name, quality=80)  # PNG なら quality は使われない
        print(name)
