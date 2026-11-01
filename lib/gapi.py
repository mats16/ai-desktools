#!/usr/bin/env python3
"""Google の API（Drive・Slides・Docs）を呼ぶ共通の部品。スライド（slides-build）・ドキュメント（docs-build）とほかのスキルのスクリプトが使う（標準ライブラリだけ）。
認証は単独で動く（gcloud も、ほかの Google のスキルも要らない）。トークンは、環境変数 GOOGLE_OAUTH_ACCESS_TOKEN、なければ
authorized_user の認証情報の JSON（GOOGLE_APPLICATION_CREDENTIALS、なければ gcloud の ADC のファイル）の refresh_token で取る。401・403 や認証情報がないときは desk-doctor で確かめる。
設定の uc_connections.proxy にあるホストは、Databricks の Unity Catalog の connection の proxy を通して呼ぶ（Google のトークンは connection が持つ。route）。
usage: python3 gapi.py --selftest"""
import datetime, functools, getpass, json, os, re, socket, subprocess, sys, tempfile, threading, time, tomllib, urllib.error, urllib.parse, urllib.request, uuid
from pathlib import Path

import desk  # ワークスペースと設定のファイルの探し方

SLIDES = "https://slides.googleapis.com/v1/presentations"
DOCS = "https://docs.googleapis.com/v1/documents"
DRIVE = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
GSLIDES = "application/vnd.google-apps.presentation"
GDOCS = "application/vnd.google-apps.document"
FOLDER = "application/vnd.google-apps.folder"
_TOK = None
_DBTOK = None  # proxy に渡す Databricks のトークン
_HOSTS = {}  # profile ごとのワークスペースの URL（取れたものだけ）
REJECTED = "connection の proxy が断った"  # proxy が自分で断ったときの ApiError の先頭（desk-doctor が見分ける）
_DBLOCK = threading.Lock()  # 取り手が並んでも、CLI を 1 回だけ呼ぶ（429 の _LOCK とは分ける。CLI は 2 分かかりうる）
WAITED = []  # 429・5xx・回線のエラーで取り直す前に待った秒（request が足す。Clock が回数と秒を出す）
_HOLD = [0.0]  # 429 の分の枠が明ける時刻。並べて取るほかの取り手も、それまで送らない
_LOCK = threading.Lock()
TIMEOUT = 120  # urlopen の秒。付けないと、つながったまま返事が来ないとき止まり続ける
SLOW = 600  # POST の urlopen の秒。pptx の変換や大きい batchUpdate は、返事が 2 分を超えうる。POST は送ったあとに切れても取り直さないので、長く待つ
RETRY = {500, 502, 503, 504}  # 一時的なサーバーのエラー。待って取り直す
# 返事を待つあいだに切れた・5xx が返ったものを取り直してよい方法（同じものを 2 回送っても結果が変わらない。PATCH も、ここでは決まった値を置くか中身を差し替えるだけ）。
# POST（batchUpdate・コピー・作る・コメントと返信）は、サーバーが受けて入れたあとに切れることがあり、取り直すと二重に入る（insertText が 2 回入る、
# コピーやコメントが 2 つできる）ので、送る前に止まったもの（UNSENT）と 429（入れる前に断る）だけを取り直す
SAFE = {"GET", "PUT", "PATCH", "DELETE"}
# 確かに送る前に止まった回線のエラー（名前を引けない・つなぐのを断られた）。urllib は送る途中のエラー（BrokenPipeError・TimeoutError）も
# URLError に包むが、socket.sendall は失敗したときにどこまで届いたかが分からないので、POST はこれだけを取り直す
UNSENT = (socket.gaierror, ConnectionRefusedError)


def window_end(body, now=None):
    """429 の本文の ErrorInfo の window_start_time（分の枠の始まり。2026-10-15 の本文では epoch の秒の文字列。ISO 8601・ミリ秒も読む）から、枠が明ける時刻（epoch 秒）。なければ None。
    上限は 1 人 1 分（quota_unit 1/min/{project}/{user}）の枠で数えるので、枠が明ければ通る（2026-10-15 に 429 の本文で確かめた。枠の始まりは分の先頭にそろっていない）。"""
    m = re.search(r'"window_start_time"\s*:\s*"?([^",}]+)', body)
    if not m:
        return None
    v = m.group(1).strip()
    try:
        if re.fullmatch(r"[\d.]+", v):  # epoch。ミリ秒なら秒にする
            t = float(v) / 1000 if float(v) > 1e11 else float(v)
        else:
            t = datetime.datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None
    end, now = t + 60 + 1, now or time.time()  # 1 秒の余裕（時計のずれ）
    return end if now - 60 < end <= now + 65 else None  # 古すぎる値と、1 分より先の値は読み違えとみなす（待ちすぎない）


class Clock:
    """工程ごとの秒を数え、標準エラーに 1 行で出す（slides.py build・gslides.py check。記録から長い回の原因を分けるため）。429 と上限を見越した待ちも出す。"""

    def __init__(self):
        self.t, self.parts = time.time(), []

    def lap(self, name):
        now = time.time()
        self.parts.append((name, now - self.t))
        self.t = now

    def show(self, what):
        waits = (f"・取り直しの待ち {len(WAITED)} 回・計 {sum(WAITED):.0f} 秒" if WAITED else "") + (f"・上限を見越した待ち {len(PACED)} 回・計 {sum(PACED):.0f} 秒" if PACED else "")
        print(f"{what}の時間（秒）: " + "・".join(f"{n} {s:.1f}" for n, s in self.parts) + f"・計 {sum(s for _, s in self.parts):.1f}{waits}"
              + ("（待ちは並べた取り手ごとの合計）" if waits else ""), file=sys.stderr)


CLOCK = Clock()  # 読み込んだときから数える


def locate():
    """(設定のファイル, ワークスペース)。探し方は desk.py（今いるフォルダから上へ desk.toml、なければ ~/.desk.toml の workspace）。なければ None。
    結果を覚えない。import のときに読むもの（slides.py の [brand]）はこちらを使う（覚えると、あとで今いるフォルダを変える desk-doctor が古い結果を使う）。"""
    return desk.locate()


@functools.cache
def find_config():
    """locate の結果（最初に呼んだときのものを覚える）。"""
    return locate()


def _found():
    """find_config の結果。なければ止まる（前のバージョンの factory.toml があれば desk-migrate、なければ desk-init を案内する）。"""
    return find_config() or sys.exit(desk.missing())


def config_path():
    """設定のファイル（ワークスペースの desk.toml か ~/.desk.toml）。"""
    return _found()[0]


def workspace():
    """ワークスペース（資料・recipes/・.desk/ を置くフォルダ）。"""
    return _found()[1]


@functools.cache
def config():
    """desk.toml の設定値（[google]・[slides]・[drive]）。"""
    return tomllib.loads(config_path().read_text())


def language():
    """資料を作る言語（desk.toml の [desk] default_language）の主の部分を小文字で（ja-JP・ja_JP・JA も ja）。書かないか設定がなければ ja（selftest は設定なしで回る）。"""
    return str((config().get("desk", {}).get("default_language") if find_config() else None) or "ja").strip().replace("_", "-").split("-")[0].lower()


def source_head():
    """出典の行頭（slides.py・docs.py が、書いていなければ足す）。ja でなければ英語（lint はどちらも出典の行と見る）。"""
    return "出典: " if language() == "ja" else "Source: "


class ApiError(Exception):
    """API がエラーを返した。メッセージは状態コード・URL・返ってきた本文。"""


ADC = "~/.config/gcloud/application_default_credentials.json"
SCOPES = ("https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/presentations",
          "https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/cloud-platform")  # cloud-platform は quota project のヘッダーに要る
LOGIN = f'gcloud auth application-default login --scopes="{",".join(SCOPES)}"'  # 認証情報の JSON を作るとき（1 回だけ）


def credentials_path():
    """authorized_user の認証情報の JSON。GOOGLE_APPLICATION_CREDENTIALS があればそれ、なければ gcloud の ADC のファイル。"""
    return Path(os.path.expanduser(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or ADC))


def refresh(creds):
    """authorized_user の refresh_token で、アクセストークンを取る（標準ライブラリだけ）。"""
    if creds.get("type") != "authorized_user":
        raise ApiError(f"認証情報の type が {creds.get('type')}。authorized_user だけ扱う（サービスアカウントはトークンを GOOGLE_OAUTH_ACCESS_TOKEN で渡す）")
    body = urllib.parse.urlencode({k: creds[k] for k in ("client_id", "client_secret", "refresh_token")} | {"grant_type": "refresh_token"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body, method="POST"), timeout=TIMEOUT) as r:
            return json.loads(r.read())["access_token"]
    except urllib.error.HTTPError as e:
        raise ApiError(f"トークンを取れない（{e.code}）。認証情報を作り直す: {LOGIN}\n{e.read().decode(errors='replace')[:500]}") from None


def file_token():
    """認証情報の JSON（credentials_path）から取る。"""
    p = credentials_path()
    if not p.is_file():
        raise ApiError(f"Google の認証情報がない: {p}。作る: {LOGIN}")
    return refresh(json.loads(p.read_text()))


def token():
    """アクセストークン。環境変数 GOOGLE_OAUTH_ACCESS_TOKEN があればそれ、なければ認証情報の JSON から取る。"""
    global _TOK
    if not _TOK:
        _TOK = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN") or file_token()
    return _TOK


def uc(cfg=None):
    """uc_connections の設定。enabled = false なら空（設定を残したまま、直接呼ぶのに戻す）。設定の型はここだけで確かめる（使う側は確かめない）。"""
    px = (config() if cfg is None else cfg).get("uc_connections", {})
    bad = [k for k, t in (("enabled", bool), ("profile", str), ("host", str), ("proxy", dict)) if k in px and not isinstance(px[k], t)] if isinstance(px, dict) else ["表"]
    if bad or not all(isinstance(n, str) for n in px.get("proxy", {}).values()):  # enabled = "false" は、文字列が真なので通してしまう
        raise ApiError(f"uc_connections の書き方が違う（{', '.join(bad) or 'proxy の名前'}）。[uc_connections] の enabled は true か false、profile・host は文字列、"
                       '[uc_connections.proxy] は "ホスト" = "connection の名前"。desk-doctor で確かめる')
    return px if px.get("enabled", True) else {}


def on_databricks():
    """Databricks の上（Genie Code・notebook・ジョブ）なら、トークンの渡し方。子のプロセスは SDK の runtime の認証を使えない（2026-11-01 にサーバーレスで確かめた）。"""
    return ("。Databricks の上では、親の Python で WorkspaceClient().config.authenticate()['Authorization'] の Bearer のあとを DATABRICKS_TOKEN に、"
            "config.host を DATABRICKS_HOST に入れて、スクリプトに渡す") if "DATABRICKS_RUNTIME_VERSION" in os.environ else ""


def profile_host(profile):
    """profile のワークスペースの URL。トークンを出す CLI に聞く（databricks auth describe。~/.databrickscfg の [DEFAULT] などの読み方を
    CLI と食い違えない）。ない profile・CLI がないなら空（ワークスペースが決まらない、として route が知らせる）。"""
    if profile not in _HOSTS:  # 取れたものだけ覚える（一時の失敗は次に聞き直す）。覚えたものを読むだけなら、トークンの取り直しを待たない
        with _DBLOCK:  # 並ぶ取り手が、そろって CLI を呼ばない
            try:
                _HOSTS.setdefault(profile, described_host(profile))
            except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError, LookupError):
                return ""
    return _HOSTS[profile]


def described_host(profile):
    r = subprocess.run(["databricks", "auth", "describe", "-p", profile, "-o", "json"], capture_output=True, text=True, errors="replace", timeout=TIMEOUT)
    host = json.loads(r.stdout)["details"]["host"]  # ない profile は host が null（2026-11-01。返す値は 0）
    if r.returncode or not (isinstance(host, str) and host):
        raise LookupError(profile)
    return host


def proxy_host(px):
    """proxy を持つ Databricks のワークスペースの URL。uc_connections.profile があればその host（トークンも同じ profile で取るので、host より先）。
    なければ uc_connections.host、なければ DATABRICKS_HOST。決まらなければ空。"""
    host = (profile_host(p) if (p := px.get("profile")) else px.get("host") or os.environ.get("DATABRICKS_HOST", "")).rstrip("/")
    return host if not host or "://" in host else f"https://{host}"


def route(url):
    """url のホストが uc_connections.proxy にあれば、その connection の proxy の URL（ホストのあとのパスと query をそのまま付ける）。なければ None。
    connection は、host を Google のホスト（https://slides.googleapis.com など）、base_path を空にして作る。"""
    px = uc()
    u = urllib.parse.urlsplit(url)
    if not (name := {h.lower(): n for h, n in px.get("proxy", {}).items()}.get(u.hostname or "")):  # ポート・大文字小文字の違いで proxy を外れない
        return None
    if not (host := proxy_host(px)):
        why = (f"databricks auth describe -p {px['profile']} で取れない（CLI がない・profile の名前が違う。databricks auth profiles で確かめる）" if px.get("profile")
               else "uc_connections.profile か uc_connections.host を書くか、DATABRICKS_HOST で渡す")
        raise ApiError(f"Databricks のワークスペースが決まらない（{why}）{on_databricks()}")
    if not host.startswith("https://"):  # Databricks のトークンを平文で送らない
        raise ApiError(f"Databricks のワークスペースの URL は https にする: {host}")
    if any(seg in (".", "..") for seg in urllib.parse.unquote(u.path).split("/")):  # proxy の外（ワークスペースのほかの API）を指させない
        raise ApiError(f"パスに . や .. がある（ファイルの ID を確かめる）: {url}")
    return f"{host}/api/2.0/unity-catalog/connections/{urllib.parse.quote(name, safe='')}/proxy{u.path}" + (f"?{u.query}" if u.query else "")


def databricks_token(proxied, stale=None):
    """proxy に渡す Databricks のトークン。ワークスペース（proxy_host）と同じところから取る: uc_connections.profile があれば、その profile で
    databricks auth token（DATABRICKS_TOKEN は使わない）。なければ DATABRICKS_TOKEN、それもなければホストで databricks auth token
    （同じホストの profile が 2 つ以上あると、CLI は profile を求める）。stale（proxy が 401 で断ったトークン）がまだ今のものなら取り直す
    （U2M のトークンは 1 時間ほどで切れ、CLI は切れかけなら新しくする。ほかの取り手がもう取り直していれば、それを使う）。"""
    global _DBTOK
    with _DBLOCK:
        if not _DBTOK or _DBTOK == stale:
            env = None if uc().get("profile") else os.environ.get("DATABRICKS_TOKEN", "").strip()
            _DBTOK = env or cli_token(urllib.parse.urlsplit(proxied).netloc)
        return _DBTOK


def cli_token(host):
    who = ["-p", p] if (p := uc().get("profile")) else ["--host", f"https://{host}"]
    login = f"ログインする: databricks auth login {' '.join(who)}（PAT の profile なら、profile を書かずに host と DATABRICKS_TOKEN で渡す）{on_databricks()}"
    try:
        r = subprocess.run(["databricks", "auth", "token", *who, "-o", "json"], capture_output=True, text=True, errors="replace", timeout=TIMEOUT)  # 読めない文字で止まらない
        if r.returncode:
            raise ApiError(f"Databricks のトークンを取れない。{login}\n{r.stderr.strip()[:500]}")
        if not (isinstance(tok := json.loads(r.stdout).get("access_token"), str) and tok):
            raise ValueError
        return tok
    except subprocess.TimeoutExpired:  # ログインの画面を待って止まった
        raise ApiError(f"databricks auth token が {TIMEOUT} 秒で返らない。{login}") from None
    except OSError as e:  # ない（FileNotFoundError）・動かせない
        raise ApiError(f"databricks の CLI を動かせない（{e}）。入れるか、トークンを DATABRICKS_TOKEN で渡す{on_databricks()}") from None
    except (ValueError, AttributeError):  # JSON でない・dict でない・access_token がない
        raise ApiError(f"databricks auth token の出力に access_token がない。{login}\n{r.stdout[:300]}") from None


def rejected(b):
    """proxy が自分で断った返事（最上位に jsonrpc と error がある JSON）なら、その中身の文字列。そうでなければ None（Google は JSON-RPC を返さない）。
    connection に人がまだログインしていないときなどに、proxy は 200 で返す（2026-11-01）。ponytail: 中身がそのまま JSON-RPC のエラーの形の
    ファイル（MCP の記録など）は、proxy を通すと落とせない。要る場面が出たら、Google から来た返事の印（ヘッダー）で見分ける"""
    if b'"jsonrpc"' not in b:  # 大きな返事・ファイルの中身を、毎回 JSON として読まない
        return None
    try:
        j = json.loads(b)
    except ValueError:  # UnicodeDecodeError も含む
        return None
    if not (isinstance(j, dict) and "jsonrpc" in j and "error" in j):
        return None
    err = j["error"]
    return str((err.get("message") if isinstance(err, dict) else None) or err)


def request(method, url, body=None, raw=None, ctype="application/json", binary=False, paced=False):
    """JSON を辞書で返す（binary=True ならバイト列）。429 は待って取り直す（サムネイルは 1 分あたりの上限がある）。5xx と回線のエラーも
    待って取り直す（POST は送る前に止まったものだけ。SAFE・UNSENT）。4 回待っても通らなければ、HTTP のエラーは ApiError、回線のエラーはそのまま上げる。
    paced=True（ページの画像）なら、送るたびに（429 の取り直しも）上限を見越して待つ（pace）。待った秒は WAITED・PACED に足す。"""
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    proxied = route(url)  # Google の認証は connection がする（proxy は Authorization を Google に送らない）
    headers = {"Authorization": f"Bearer {databricks_token(proxied) if proxied else token()}", "Content-Type": ctype}
    if not proxied and (qp := config().get("google", {}).get("quota_project")):
        headers["x-goog-user-project"] = qp  # gcloud の既定の OAuth クライアントで取ったトークンは、これがないと 403
    url, renewed = proxied or url, False
    for wait in (5, 15, 30, 60, None):
        if (hold := _HOLD[0] - time.time()) > 0:  # ほかの取り手が 429 を受け、分の枠が明けるのを待っている
            WAITED.append(hold)
            time.sleep(hold)
        if paced:
            pace()
        try:
            req = urllib.request.Request(url, data=data, headers={k: v for k, v in headers.items() if not (proxied and k == "Authorization")}, method=method)
            if proxied:  # urllib はリダイレクト先にもヘッダーを写す。proxy の外（Drive のダウンロードの先など）に Databricks のトークンを送らない
                req.add_unredirected_header("Authorization", headers["Authorization"])
            with urllib.request.urlopen(req, timeout=TIMEOUT if method in SAFE else SLOW) as r:
                b = r.read()
                if proxied and (why := rejected(b)) is not None:
                    raise ApiError(f"{REJECTED}: {method} {url}\n{why[:2000]}")
                if binary or not b:
                    return b if binary else {}
                try:
                    return json.loads(b)
                except ValueError:  # Google は JSON を返す。proxy の画面（HTML など）なら、トレースバックでなく ApiError
                    if proxied:
                        raise ApiError(f"connection の proxy が JSON でない返事をした: {method} {url}\n{b[:500].decode(errors='replace')}") from None
                    raise
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            # Databricks のトークンが切れた（Databricks の返事は {"error_code": …}。Google が connection を通して返す 401 は {"error": {…}} で、取り直しても直らない）。
            # 取り直して、新しいトークンなら 1 回だけ送り直す（断られた要求は入っていない）
            if e.code == 401 and proxied and wait and not renewed and '"error_code"' in body:
                renewed, old = True, headers["Authorization"].removeprefix("Bearer ")
                try:
                    new = databricks_token(proxied, stale=old)
                except ApiError as r:  # 取り直せなかった。どの要求が断られたかも残す
                    raise ApiError(f"{e.code} {method} {url}（Databricks のトークンを取り直せない: {r}）\n{body[:2000]}") from None
                if new != old:
                    headers["Authorization"] = f"Bearer {new}"
                    continue
            if e.code == 429 and wait:
                with _LOCK:  # 枠が分かれば、明けるまで待つ（取り手がそろって 5・15・30 秒待つより短い）。分からないか、もう明けている（時計のずれ）なら、5・15・30・60 秒
                    end = window_end(body)
                    if end and end > time.time():
                        _HOLD[0] = max(_HOLD[0], end)
                        w = _HOLD[0] - time.time()
                    else:
                        w = wait
                WAITED.append(w)
                time.sleep(w)
                continue
            if e.code in RETRY and wait and method in SAFE:
                WAITED.append(wait)
                time.sleep(wait)
                continue
            raise ApiError(f"{e.code} {method} {url}\n{body[:2000]}") from None
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            # urllib は、つなぐ・送るあいだのエラーを URLError に包み、送ったあと（返事を待つ・読むあいだ）のエラー（RemoteDisconnected・
            # ConnectionResetError・TimeoutError）はそのまま上げる
            if wait and (method in SAFE or isinstance(getattr(e, "reason", None), UNSENT)):
                WAITED.append(wait)
                time.sleep(wait)
                continue
            raise


def batch(pid, reqs):
    """presentations.batchUpdate。まとめて送った要求は、どれか 1 つが失敗すると全部が入らない。"""
    return request("POST", f"{SLIDES}/{pid}:batchUpdate", {"requests": reqs}) if reqs else {}


def file_id(s):  # Google Slides・Docs の URL か ID
    m = re.search(r"/d/([\w-]+)", s)
    return m.group(1) if m else s


def folder_id(s):  # Drive のフォルダの URL か ID
    m = re.search(r"/folders/([\w-]+)", s)
    return m.group(1) if m else s


def subfolder(root, name, create=False):
    """root（フォルダの URL か ID）の下の name のフォルダの ID。なければ None（create なら作る）。2 つあれば古いほう（作るのと探すのとで同じものを選ぶ）。"""
    q = urllib.parse.quote(f"name = '{name}' and '{folder_id(root)}' in parents and mimeType = '{FOLDER}' and trashed = false")
    found = request("GET", f"{DRIVE}/files?q={q}&orderBy=createdTime&fields=files(id)&supportsAllDrives=true&includeItemsFromAllDrives=true")["files"]
    if found:
        return found[0]["id"]
    if not create:
        return None
    return request("POST", f"{DRIVE}/files?supportsAllDrives=true&fields=id", {"name": name, "mimeType": FOLDER, "parents": [folder_id(root)]})["id"]


def upload(data, mime, name=None, parent=None, convert=None, fid=None, fields="id"):
    """Drive にファイルを上げる。fid を渡すと中身だけ上書きする（ID・URL・共有の設定は変わらない）。
    convert に Google の形式（GSLIDES など）を渡すと変換して作る。"""
    q = f"supportsAllDrives=true&fields={fields}"
    if fid:
        return request("PATCH", f"{UPLOAD}/{fid}?uploadType=media&{q}", raw=data, ctype=mime)
    b = uuid.uuid4().hex
    meta = json.dumps({"name": name, **({"parents": [parent]} if parent else {}), **({"mimeType": convert} if convert else {})})  # parent を省くと My Drive の直下
    body = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n--{b}\r\nContent-Type: {mime}\r\n\r\n".encode()
            + data + f"\r\n--{b}--".encode())
    return request("POST", f"{UPLOAD}?uploadType=multipart&{q}", raw=body, ctype=f"multipart/related; boundary={b}")


def delete(fid):  # ゴミ箱を通さずに消す。作った仮のファイルを片付けるときだけ使う
    request("DELETE", f"{DRIVE}/files/{fid}?supportsAllDrives=true")


def trash(fid):  # ゴミ箱に移す（30 日は戻せる）。共有ドライブの資料のフォルダに作ったものを片付けるときに使う
    request("PATCH", f"{DRIVE}/files/{fid}?supportsAllDrives=true", {"trashed": True})


def guard(fid, rev, key, src, stop=True):
    """前に組んだあとに画面で直されていたら（rev が key に残したリビジョンか指紋と違う）、または未解決のコメントがあれば、止める。
    組み直すと画面での修正は消え、コメントは付け先を失う。src は直しを入れる先（pages.py・doc.md）。stop=False なら止めずに理由の並びを返す（slides.py plan）。"""
    last = request("GET", f"{DRIVE}/files/{fid}?supportsAllDrives=true&fields=appProperties").get("appProperties", {}).get(key)
    st = workspace() / ".desk" / "comments.json"  # 見張りの知らせ（deck-workflow の comments.py watch）は、直すコメントでないので数えない
    notice = {n["id"] for n in json.loads(st.read_text()).get("notice", {}).values()} if st.is_file() else set()
    comments = [c for c in request("GET", f"{DRIVE}/files/{fid}/comments?pageSize=100&fields=comments(id,resolved,deleted,content,quotedFileContent(value))")
                .get("comments", []) if not c.get("resolved") and not c.get("deleted") and c.get("id") not in notice]
    for c in comments[:5]:  # どの文に付いた、どんなコメントか（直す先を探しやすいように）
        print(f"コメント: 「{c.get('quotedFileContent', {}).get('value', '')[:30]}」に「{c.get('content', '')[:60]}」", file=sys.stderr)
    why = (["前に組んだあとに画面で直されている"] if last and last != rev else []) + ([f"未解決のコメントが {len(comments)} 件ある"] if comments else [])
    if why and not stop:
        return why
    if why:
        sys.exit("組み直すと、画面での修正が消え、コメントは付け先を失う: " + "、".join(why)
                 + f"。直しとコメントへの対応を {src} に入れてから、--force を付けて組み直す（コメントを全部見るのは deck-workflow の comments.py）")


def stamp(fid, rev, key):  # 組んだときのリビジョンを、Drive のファイルの appProperties に残す（guard が比べる）
    request("PATCH", f"{DRIVE}/files/{fid}?supportsAllDrives=true&fields=id", {"appProperties": {key: rev}})


def slide_ids(pid):
    return [s["objectId"] for s in request("GET", f"{SLIDES}/{pid}?fields=slides(objectId)").get("slides", [])]


def user():
    """この機械の使っている人の名前。手元の記録のファイルを人ごとに分ける（Linux の /tmp は人で共有する）。取れなければ "user"。"""
    try:
        return getpass.getuser()
    except Exception:  # 環境変数も passwd もない（コンテナなど）。getpass はバージョンによって OSError か KeyError を出す
        return "user"


THUMB_PER_MIN = 60  # ページの画像は 1 人 1 分 60 回まで（Slides API の expensive read。https://developers.google.com/workspace/slides/api/limits）
THUMB_LOG = os.path.join(tempfile.gettempdir(), f"gapi_thumbnails_{user()}")  # この機械で画像を取った時刻。ほかの会話・子の確認と上限を分け合う（上限は人ごとなので、ファイルも人ごと）
PACED = []  # 上限を見越して待った秒（pace が足す）


def pace(path=THUMB_LOG, limit=THUMB_PER_MIN, window=61):
    """ページの画像を取る前に呼ぶ。この機械で直前の window 秒に limit 回取っていたら、空くまで待つ（超えると 429 で、分の枠が明けるまで止まる。
    前のバージョンの 5・15・30 秒の取り直しでは、2026-10-15 に 53 枚で測ると、最後の 6 枚が 52 秒ずつ待った）。ponytail: ほかの機械（CI など）で同じ人が取った分は数えない（429 の取り直しが拾う）"""
    try:
        import fcntl
    except ImportError:  # Windows。見越さない（429 の取り直しが拾う）
        return
    while True:
        try:
            with open(path, "a+") as f:
                fcntl.flock(f, fcntl.LOCK_EX)  # 同じ機械の会話・子が同じファイルを読み書きする
                f.seek(0)
                now = time.time()
                ts = sorted(float(t) for t in re.findall(r"\d+(?:\.\d+)?", f.read()) if now - float(t) < window)  # 数でないものは読み飛ばす
                if len(ts) < limit:
                    f.seek(0)
                    f.truncate()
                    f.write(" ".join(map(str, ts + [now])))
                    return
        except OSError:  # 読み書きできなければ見越さない（429 の取り直しが拾う）
            return
        PACED.append(w := ts[len(ts) - limit] + window - now)
        time.sleep(w)


def thumbnail(pid, obj):
    """Google が描いたページの画像（1600 × 900）の情報。contentUrl は 30 分で切れ、知っていれば誰でも開ける（人に見せない）。上限を見越して待つ（pace）。"""
    return request("GET", f"{SLIDES}/{pid}/pages/{obj}/thumbnail?thumbnailProperties.thumbnailSize=LARGE&thumbnailProperties.mimeType=PNG", paced=True)


def u16(s):  # Slides API・Docs API の文字位置は UTF-16 の単位
    return len(s.encode("utf-16-le")) // 2


def png(url, w=1024):
    """SVG の URL を、Slides API が読める PNG の URL にする（wsrv.nl が幅 w px に描く）。Slides API は SVG の URL を読めない（slides-build/images.md）。"""
    return "https://wsrv.nl/?" + urllib.parse.urlencode({"url": url, "output": "png", "w": w})


def carry(paths):
    """手元の画像（PNG・JPG・GIF・SVG）を Slides API が読める URL にする。API は公開された URL の画像しか読めないので、pptxgenjs で 1 枚に
    1 つずつ入れた pptx を Drive で Google Slides に変換し、その画像の URL（30 分で切れる）を取る。SVG は API が貼れないので sharp で PNG にする。
    [deck-google-010] slides.py・docs.py の build の中で呼ぶので、pages.py では手元のパスを d.image に渡すだけでよい。戻り: (URL の並び, あとで消す仮のファイルの ID)。"""
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "images.pptx")
        js = ("const p = new (require('pptxgenjs'))(); p.layout = 'LAYOUT_WIDE';"
              "(async () => { for (const f of process.argv.slice(2)) {"
              "  const src = /\\.svg$/i.test(f) ? { data: 'image/png;base64,' + (await require('sharp')(f, { density: 600 })"
              "    .resize({ width: 1600, withoutEnlargement: true }).png().toBuffer()).toString('base64') } : { path: f };"
              "  p.addSlide().addImage({ ...src, x: 0, y: 0, w: 1, h: 1 }); }"
              "  await p.writeFile({ fileName: process.argv[1] }); })();")
        root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["node", "-e", js, out, *paths], check=True, env={**os.environ, "NODE_PATH": root})
        # [deck-google-011] 仮のファイルは My Drive の直下に置く（フォルダの ID を持つと、スクリプトをほかの人に渡したときに動かない）
        fid = upload(open(out, "rb").read(), PPTX, "tmp_images", convert=GSLIDES)["id"]
    try:
        p = request("GET", f"{SLIDES}/{fid}?fields=slides(pageElements(image(contentUrl)))")
        return [s["pageElements"][0]["image"]["contentUrl"] for s in p["slides"]], fid
    except BaseException:
        delete(fid)
        raise


def run(main):
    """CLI の入り口。API のエラーは、返ってきた本文を見せて終える（トレースバックにしない）。"""
    try:
        main()
    except ApiError as e:
        sys.exit(str(e))


def selftest():
    assert file_id("https://docs.google.com/presentation/d/1AbC-_x/edit#slide=id.p") == "1AbC-_x" and file_id("1AbC") == "1AbC"
    assert folder_id("https://drive.google.com/drive/folders/1Xy_z-9?usp=sharing") == "1Xy_z-9" and folder_id("1Xy") == "1Xy"
    try:
        refresh({"type": "service_account"})
        raise AssertionError("サービスアカウントを通した")
    except ApiError as e:
        assert "authorized_user" in str(e)
    t0 = 1_760_000_000
    assert window_end('{"metadata": {"window_start_time": "2025-10-09T08:53:20Z"}}', t0) == t0 + 61
    body = '"quota_limit": "ExpensiveReadRequestsPerMinutePerUser",\n          "window_start_time": "1760000000",\n          "service": "slides.googleapis.com"'  # 429 の本文の形（2026-10-15）
    assert window_end(body, t0) == t0 + 61
    assert window_end('"window_start_time": "1760000000000"', t0) == t0 + 61 and window_end('"window_start_time": 1760000000', t0) == t0 + 61
    assert window_end('"window_start_time": "%d"' % (t0 + 3600), t0) is None  # 1 時間先は読み違え（そこまで待たない）
    assert window_end("{}", t0) is None and window_end('"window_start_time": "x"', t0) is None and window_end('"window_start_time": "1"', t0) is None
    import http.client, io
    from unittest import mock
    real = urllib.request.urlopen, time.sleep, config, globals()["_TOK"], globals()["pace"]
    calls, slept, paced = [], [], []

    def fake(req, *a, **k):  # 1 回目は、もう明けた枠の 429。2 回目は通す
        calls.append(req)
        if len(calls) == 1:
            raise urllib.error.HTTPError(req.full_url, 429, "x", {}, io.BytesIO(b'"window_start_time": "%d"' % (time.time() - 70)))
        return io.BytesIO(b"{}")

    globals().update(config=lambda: {}, _TOK="t", pace=lambda: paced.append(1))
    urllib.request.urlopen, time.sleep = fake, slept.append
    try:
        assert request("GET", "https://example.invalid", paced=True) == {} and slept == [5]  # 明けた枠なら、0.5 秒でなく前の 5 秒で取り直す
        assert len(paced) == 2  # 取り直しも、上限を見越して数える
        calls.clear()
        _HOLD[0] = time.time() + 30  # ほかの取り手が 429 で枠を待っている
        calls.append(0)  # 1 回目を 429 にしない
        assert request("GET", "https://example.invalid") == {} and 25 < slept[-1] <= 30 and len(WAITED) == 2  # 枠を待った秒も数える

        def answers(*rs):  # urlopen が順に返すもの（例外なら上げる）。最後のものを繰り返す
            calls.clear()
            slept.clear()
            WAITED.clear()
            _HOLD[0] = 0.0

            def f(req, *a, timeout=None, **k):
                assert timeout == (TIMEOUT if req.get_method() in SAFE else SLOW)
                r = rs[min(len(calls), len(rs) - 1)]
                calls.append(req)
                if isinstance(r, int):  # 401 は Databricks の返事の形（proxy のトークンが切れた）
                    raise urllib.error.HTTPError(req.full_url, r, "x", {}, io.BytesIO(b'{"error_code": 401}' if r == 401 else b"{}"))
                if isinstance(r, Exception):
                    raise r
                return io.BytesIO(r)
            urllib.request.urlopen = f
        answers(http.client.RemoteDisconnected("Remote end closed connection without response"), b'{"a": 1}')
        assert request("GET", "https://example.invalid") == {"a": 1} and slept == [5] and WAITED == [5]
        answers(503)
        try:
            request("GET", "https://example.invalid")
            raise AssertionError("503 が続いても通した")
        except ApiError as e:
            assert str(e).startswith("503 GET") and len(calls) == 5 and slept == [5, 15, 30, 60]
        sending = (urllib.error.URLError(BrokenPipeError()), urllib.error.URLError(TimeoutError("timed out")))  # 送る途中で切れた（どこまで届いたか分からない）
        for r, method in ((400, "GET"), (http.client.RemoteDisconnected("x"), "POST"), (503, "POST"), *((e, "POST") for e in sending)):  # 400 と、送ったかもしれない POST は取り直さない
            answers(r, b"{}")
            try:
                request(method, "https://example.invalid", {})
                raise AssertionError(f"{r} の {method} を取り直した")
            except (ApiError, OSError):
                assert len(calls) == 1 and not slept
        for e in (urllib.error.URLError(ConnectionRefusedError()), urllib.error.URLError(socket.gaierror(8, "nodename nor servname"))):  # 送る前に止まった POST は取り直す
            answers(e, b"{}")
            assert request("POST", "https://example.invalid", {}) == {} and len(calls) == 2
        answers(*sending, b"{}")  # GET なら、送る途中で切れても取り直す
        assert request("GET", "https://example.invalid") == {} and len(calls) == 3
        globals().update(_DBTOK="d", config=lambda: {"google": {"quota_project": "q"}, "uc_connections": {"host": "dbc.example/", "proxy": {"slides.googleapis.com": "gs"}}})
        answers(b"{}")
        request("POST", f"{SLIDES}/p:batchUpdate?fields=x", {})
        request("GET", f"{DRIVE}/about")
        (a, b), h = calls, "X-goog-user-project"
        assert route(f"{SLIDES}/p") and not uc({"uc_connections": {"enabled": False, "proxy": {"slides.googleapis.com": "gs"}}})  # 書いたまま止められる
        assert a.has_header("Authorization") and "Authorization" not in a.headers  # リダイレクトでは写さない
        with mock.patch.dict(globals(), config=lambda: {"uc_connections": {"host": "h.example", "proxy": {"slides.googleapis.com": "a/b"}}}):
            assert "/connections/a%2Fb/proxy/" in route(f"{SLIDES}/p") and route("https://Slides.googleapis.com:443/v1/p")  # 名前の / で、proxy のパスを変えない。ポート・大文字でも外れない
            for bad in (f"{SLIDES}/../../clusters/list", f"{SLIDES}/x/%2e%2e/y"):
                try:
                    route(bad)
                    raise AssertionError(f"{bad} を通した")
                except ApiError:
                    pass
        with mock.patch.dict(globals(), config=lambda: {"uc_connections": {"host": "http://h.example", "proxy": {"slides.googleapis.com": "gs"}}}):
            try:
                route(f"{SLIDES}/p")
                raise AssertionError("http を通した")
            except ApiError as e:
                assert "https" in str(e)
        answers(b"<html>sign in</html>")
        try:
            request("GET", f"{SLIDES}/p")
            raise AssertionError("JSON でない返事を通した")
        except ApiError as e:
            assert "JSON でない" in str(e)
        for bad in ({"proxy": "gs"}, {"proxy": {"slides.googleapis.com": 5}}, "on", {"enabled": "false", "proxy": {"slides.googleapis.com": "gs"}},
                    {"profile": 5, "proxy": {"slides.googleapis.com": "gs"}}, {"host": 5, "proxy": {"slides.googleapis.com": "gs"}}):  # 表でない・名前が文字列でない設定は、トレースバックでなく ApiError
            with mock.patch.dict(globals(), config=lambda: {"uc_connections": bad}):
                try:
                    route(f"{SLIDES}/p")
                    raise AssertionError(f"{bad!r} を通した")
                except ApiError:
                    pass
        assert a.full_url == "https://dbc.example/api/2.0/unity-catalog/connections/gs/proxy/v1/presentations/p:batchUpdate?fields=x"
        assert a.get_header("Authorization") == "Bearer d" and not a.has_header(h)  # quota project は Google のトークンの持ち主の側の話
        assert b.full_url == f"{DRIVE}/about" and b.get_header("Authorization") == "Bearer t" and b.get_header(h) == "q"  # connection のないホストは直接
        def describe(cmd, **k):  # databricks auth describe の出力の形（2026-11-01。ない profile も 0 で返し、host は null）
            host = {"p1": "https://dbc-p1.example/"}.get(cmd[cmd.index("-p") + 1])
            return subprocess.CompletedProcess(cmd, 0, json.dumps({"status": "ok", "details": {"host": host}}), "")
        _HOSTS.clear()
        with mock.patch.object(subprocess, "run", describe):
            assert proxy_host({"profile": "p1"}) == "https://dbc-p1.example" and proxy_host({"profile": "p1", "host": "h.example"}) == "https://dbc-p1.example"  # トークンと同じ profile
            assert proxy_host({"profile": "nope", "host": "h.example"}) == ""  # ない profile は、ほかのワークスペースに落とさない
        with mock.patch.object(subprocess, "run", side_effect=FileNotFoundError):
            assert profile_host("p1") == "https://dbc-p1.example/" and profile_host("p2") == ""  # 取れたものは覚え、CLI がなければ決まらないとして知らせる
        with mock.patch.object(subprocess, "run", describe):
            assert profile_host("p2") == ""
        _HOSTS.clear()
        for body in (b'{"jsonrpc":"2.0","error":{"code":-32600,"message":"Please login first"}}', b'{"error":"Please login first","id":1,"jsonrpc":"2.0"}'):
            answers(body)
            try:
                request("GET", f"{SLIDES}/p")
                raise AssertionError("proxy の JSON-RPC のエラーを通した")
            except ApiError as e:
                assert "Please login first" in str(e)
        assert rejected(b'{"error": {"code": 404}}') is None and rejected(b"%PDF-1.4 {") is None and rejected(b'{"files": [{"name": "jsonrpc"}]}') is None  # Google の返事・ファイルの中身は通す
        assert rejected(b'{"jsonrpc": "2.0", "error": {"code": 1, "message": null}}') == "{'code': 1, 'message': None}" and rejected(b'{"jsonrpc": "2.0", "error": {"message": 5}}') == "5"
        assert rejected(b'{"jsonrpc": "2.0", "error": {"message": "' + b"x" * 9000 + b'"}}')  # 長い断りも拾う
        renewals = []
        globals()["cli_token"], real_cli = (lambda host: renewals.append(host) or "d2"), cli_token
        try:
            answers(401, b'{"ok": 1}')  # 切れたトークンは、取り直して 1 回だけ送り直す
            assert request("POST", f"{SLIDES}/p:batchUpdate", {}) == {"ok": 1} and renewals == ["dbc.example"] and calls[-1].get_header("Authorization") == "Bearer d2"
            answers(urllib.error.HTTPError("u", 401, "x", {}, io.BytesIO(b'{"error": {"code": 401, "status": "UNAUTHENTICATED"}}')))  # Google の 401 は取り直さない
            n = len(renewals)
            try:
                request("GET", f"{SLIDES}/p")
                raise AssertionError("Google の 401 を通した")
            except ApiError:
                assert len(calls) == 1 and len(renewals) == n
            answers(401)  # 取り直しても同じトークン（DATABRICKS_TOKEN など）なら、送り直さない
            try:
                request("GET", f"{SLIDES}/p")
                raise AssertionError("同じトークンで送り直した")
            except ApiError:
                assert len(calls) == 1
            globals()["cli_token"] = lambda host: renewals.append(host) or f"d{len(renewals) + 2}"  # 取り直すたびに新しいトークン
            answers(401)  # 新しいトークンでも 401 なら、それ以上は送らない
            try:
                request("GET", f"{SLIDES}/p")
                raise AssertionError("401 を何度も送り直した")
            except ApiError:
                assert len(calls) == 2
            globals()["cli_token"] = lambda host: (_ for _ in ()).throw(ApiError("Databricks のトークンを取れない"))
            answers(401)  # 取り直せないときも、断られた要求を残す
            try:
                request("GET", f"{SLIDES}/p")
                raise AssertionError("取り直せないのを通した")
            except ApiError as e:
                assert str(e).startswith("401 GET https://dbc.example/") and "取り直せない" in str(e)
            globals()["cli_token"] = lambda host: renewals.append(host) or "d2"
            answers(500, 500, 500, 500, 401)  # 最後の回の 401 も、None を返さずに ApiError
            try:
                request("GET", f"{SLIDES}/p")
                raise AssertionError("最後の回の 401 を通した")
            except ApiError:
                assert len(calls) == 5
            globals()["_DBTOK"] = None
            with mock.patch.dict(os.environ, DATABRICKS_TOKEN=" \n"):
                assert databricks_token(f"{SLIDES}/p") == "d2"  # 空白だけの環境変数は、ないものとする
            globals()["_DBTOK"] = None
            with mock.patch.dict(os.environ, DATABRICKS_TOKEN="env\n"):
                assert databricks_token(f"{SLIDES}/p") == "env"  # profile がなければ環境変数（ファイルから読んだ改行は外す）
                globals().update(_DBTOK=None, config=lambda: {"uc_connections": {"profile": "p1", "proxy": {"slides.googleapis.com": "gs"}}})
                n = len(renewals)
                assert databricks_token(f"{SLIDES}/p") == "d2" and len(renewals) == n + 1  # profile があれば、ワークスペースと同じ profile で取る
                assert databricks_token(f"{SLIDES}/p", stale="old") == "d2" and len(renewals) == n + 1  # ほかの取り手がもう取り直していれば、CLI を呼ばない
        finally:
            globals()["cli_token"] = real_cli
    finally:
        urllib.request.urlopen, time.sleep = real[0], real[1]
        globals().update(config=real[2], _TOK=real[3], pace=real[4], _DBTOK=None)
        WAITED.clear()
        _HOLD[0] = 0.0
    with tempfile.TemporaryDirectory() as d:  # 上限に届いたら、いちばん古い 1 回が窓を出るまで待つ
        log = os.path.join(d, "t")
        open(log, "w").write(f"{time.time() - 0.6} {time.time() - 0.5}")
        t0 = time.time()
        pace(log, limit=3, window=0.8)
        assert time.time() - t0 < 0.1 and not PACED
        pace(log, limit=3, window=0.8)
        assert 0.1 < time.time() - t0 < 0.5 and len(PACED) == 1 and len(open(log).read().split()) <= 3
        open(log, "w").write("x 1.5.6")  # 壊れた中身は読み飛ばす
        pace(log, limit=3, window=0.8)
        assert len(PACED) == 1
        pace(os.path.join(d, "no", "such"), limit=3)  # 書けないところでも止まらない
    print("selftest ok")


if __name__ == "__main__":
    sys.exit(selftest() if sys.argv[1:] == ["--selftest"] else __doc__)
