#!/usr/bin/env python3
"""スピーカーノートを読み書きする部品と、デッキのテーマの目印・書体・リビジョン。持ち主は google-slides（slides.py・lint.py が import する）。
google-vids は、この写しを持つ（同じ中身。直すのは google-slides のものだけで、tests/skills/check.py --sync で写す）。標準ライブラリと gapi・brand だけ。"""
import hashlib, re, sys, urllib.parse

import gapi
from brand import FONT, FONT_EM, JP_FONTS

# テーマの目印。マスターのページ番号の枠の代替テキストに、名前と、マスターの配色・書体・レイアウトの目印に入らない値（theme_extras の JSON）を書く。
# Drive の複製でも残る（2026-10-13）ので、デッキはテーマの値をすべて持ち、theme_from で theme.json に戻せる
THEME_MARK = re.compile(r"ai-deck-factory theme=([A-Za-z0-9_-]+)(?: (\{.*\}))?", re.S)

DECK_FIELDS = ("masters(objectId,pageProperties,pageElements(objectId,description,shape)),"
               "layouts(objectId,layoutProperties,pageElements(objectId,description,shape(placeholder)))")  # テーマを読む・当てるのに要るもの（theme_from・theme_reqs）


STAMP = "slides_py_revision"  # 組んだときのリビジョン（revision）を、Drive のファイルの appProperties に残す


def revision(pid):
    """Drive のリビジョンの一覧の最後の ID。中身を直すと進み、コメント・返信・解決と appProperties の書き込みでは進まない。presentations の revisionId は
    コメントを付けても返信しても解決しても進み、comments.py reply --resolve のあとの build が画面で直されたと取り違えるので使わない（2026-10-19 に確かめた）。"""
    last, page = None, None
    while True:  # 古い順に並ぶ
        r = gapi.request("GET", f"{gapi.DRIVE}/files/{pid}/revisions?pageSize=1000&fields=nextPageToken,revisions(id)" + (f"&pageToken={urllib.parse.quote(page)}" if page else ""))
        last = (r.get("revisions") or [{"id": last}])[-1]["id"]
        if not (page := r.get("nextPageToken")):
            return last


def deck_mark(p):
    """presentations の masters・layouts の代替テキストにある、テーマの目印（THEME_MARK の match）。なければ None（template.py で合わせ直す前のテンプレートから作ったデッキ）。"""
    return next((m for pg in p.get("masters", []) + p.get("layouts", []) for e in pg.get("pageElements", [])
                 if (m := THEME_MARK.search(e.get("description", "")))), None)


def deck_theme(p):
    """デッキ p のテーマの名前（deck_mark）。なければ None。"""
    return m.group(1) if (m := deck_mark(p)) else None


def deck_font(p):
    """デッキの書体。テンプレートのマスターのプレースホルダーの書体（template.py が書く。本文の枠を先に見る）のうち、JP_FONTS にあるもの。
    欧文の書体（FONT_EM の DM Sans）は、template.py が書いたテーマの名前（deck_theme）があるデッキだけ。
    なければ FONT（社内資料の複製など、マスターが欧文の書体のデッキは FONT で組み、lint も FONT と比べる）。pages.py は FONT で組み、build が置き換える。"""
    fonts = JP_FONTS | set(FONT_EM) if deck_theme(p) else JP_FONTS
    els = [e for m in p.get("masters", []) for e in m.get("pageElements", []) if "placeholder" in e.get("shape", {})]
    for e in sorted(els, key=lambda e: e["shape"]["placeholder"].get("type") != "BODY"):
        for t in e["shape"].get("text", {}).get("textElements", []):
            if (f := t.get("textRun", {}).get("style", {}).get("fontFamily")) in fonts:
                return f
    return FONT


def mag(d):
    return d.get("magnitude", 0) * (12700 if d.get("unit") == "PT" else 1)


def flatten(els, g=(1, 1, 0, 0)):
    """グループをほどき、(要素, [x, y, w, h]) を重なりの順に返す（EMU）。グループの変形は縮尺と移動だけを合成する。"""
    for e in els:
        t = e.get("transform", {})
        one = 0 if t else 1  # API の JSON は 0 の値を省く（横の線は scaleY、縦の線は scaleX がない）。2026-10-08 まで 1 と読み、線の検査が効いていなかった
        sx, sy = t.get("scaleX", one) * g[0], t.get("scaleY", one) * g[1]
        tx, ty = g[0] * t.get("translateX", 0) + g[2], g[1] * t.get("translateY", 0) + g[3]
        if "elementGroup" in e:
            yield from flatten(e["elementGroup"].get("children", []), (sx, sy, tx, ty))
            continue
        w, h = mag(e.get("size", {}).get("width", {})) * sx, mag(e.get("size", {}).get("height", {})) * sy
        yield e, [min(tx, tx + w), min(ty, ty + h), abs(w), abs(h)]


def paras(text):
    """段落ごとに (段落の書式, [(文字, 書式), …]) を返す。段落の中の改行（\\v）は文字に残す。箇条書きの段落は書式に bullet: True を足す。"""
    out = []
    for te in (text or {}).get("textElements", []):
        if "paragraphMarker" in te:
            out.append((te["paragraphMarker"].get("style", {}) | ({"bullet": True} if "bullet" in te["paragraphMarker"] else {}), []))
        elif "textRun" in te and out:
            out[-1][1].append((te["textRun"]["content"].replace("\n", ""), te["textRun"].get("style", {})))
    return out


def ptext(para):
    return "".join(c for c, _ in para[1]).replace("\v", " ")


def note_text(s):
    """ページのスピーカーノートの文字。"""
    notes = s.get("slideProperties", {}).get("notesPage", {})
    spk = notes.get("notesProperties", {}).get("speakerNotesObjectId")
    return "\n".join(ptext(x) for e, _ in flatten(notes.get("pageElements", [])) if e["objectId"] == spk
                     for x in paras(e.get("shape", {}).get("text")))


def notes_of(slides):
    """ページの番号（"1" から）→ スピーカーノートの文字（末尾の改行は落とす。Slides が読み返すときに付ける）。"""
    return {str(i): note_text(s).rstrip("\n") for i, s in enumerate(slides, 1)}


def note_reqs(slides, script, font):
    """ノートを script（ページの番号 → 文字。None のページは触らない）に書き換える要求。変わらないページは書かない。"""
    reqs, before = [], notes_of(slides)
    for i, s in enumerate(slides, 1):
        if (t := script[str(i)]) is None or t == before[str(i)]:
            continue
        nid = s["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"]  # 枠がまだなくても、insertText が作る
        if before[str(i)]:
            reqs.append({"deleteText": {"objectId": nid, "textRange": {"type": "ALL"}}})
        if t:
            reqs += [{"insertText": {"objectId": nid, "insertionIndex": 0, "text": t}},
                     {"updateTextStyle": {"objectId": nid, "textRange": {"type": "ALL"}, "style": {"fontFamily": font}, "fields": "fontFamily"}}]
    return reqs


PAGE_KEY = re.compile(r"k([0-9a-f]{8})h[0-9a-f]{16}$")  # JSON のページのファイル名の印（page_key）。中身のハッシュの前に入れる


def page_key(name):
    """JSON のページのファイル名 name の印（8 けた）。並べ替えても中身が変わっても、前に組んだ同じページのスライドを探せる（ファイルを選んで組むとき）。"""
    return hashlib.sha1(name.encode()).hexdigest()[:8]


def selftest():
    p = {"masters": [{"pageElements": [{"objectId": "m", "description": "ai-deck-factory theme=navy", "shape": {"placeholder": {"type": "BODY"}, "text": {"textElements": [{"textRun": {"style": {"fontFamily": sorted(JP_FONTS)[0]}}}]}}}]}]}
    assert deck_theme(p) == "navy" and deck_font(p) == sorted(JP_FONTS)[0] and deck_font({}) == FONT
    s = {"slideProperties": {"notesPage": {"notesProperties": {"speakerNotesObjectId": "n"}, "pageElements": [
        {"objectId": "n", "shape": {"text": {"textElements": [{"paragraphMarker": {}}, {"textRun": {"content": "読み上げ\n"}}]}}}]}}}
    assert note_text(s) == "読み上げ" and notes_of([s]) == {"1": "読み上げ"} and note_reqs([s], {"1": "読み上げ"}, FONT) == []
    revs = {"": {"revisions": [{"id": "1"}, {"id": "4"}], "nextPageToken": "t+1"}, "t%2B1": {"revisions": [{"id": "8"}], "nextPageToken": "t2"}, "t2": {}}
    saved, gapi.request = gapi.request, lambda m, u, *a, **k: revs[u.partition("pageToken=")[2]]
    try:
        assert revision("x") == "8"  # リビジョンの一覧は古い順。最後のページの最後の ID（空のページが続いても前の ID）
    finally:
        gapi.request = saved
    assert PAGE_KEY.search(f"x_k{page_key('p01')}h{'0' * 16}").group(1) == page_key("p01")
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    sys.exit(__doc__)
