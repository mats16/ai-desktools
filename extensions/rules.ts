// pi の側のつなぎ: read・bash の結果に、その作業（読んだパス・コマンドと、出力に中身が出たファイルで見る）で出すワークスペースのレシピ（recipes/<名前>/RECIPE.md）と、顧客の memory.md・構成案の「使う決まり」を足す。/skill:<名前> で呼んだスキルには、その SKILL.md を読んだときと同じものを足す（今の文脈に残るものは足さない）。中身は hooks/rules_overlay.py（Claude Code・Codex と共有）
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = join(dirname(fileURLToPath(import.meta.url)), "..", "hooks", "rules_overlay.py");
const PART = /(?:^|\n)## (?:ワークスペースの決まり(?:の一覧)?|顧客の memory): /;  // 足したものの頭（rules_overlay.py の見出しの形）
const TYPE = "desk-tools-rules";  // /skill:<名前> のときに足すメッセージ

export default function (pi: any) {
  let turn = "";  // このターンに足したもの。pi は同じメッセージの道具を並べて動かし、互いの結果はまだ文脈に載っていない

  function overlay(ctx: any, text: string, isPath: boolean, nested = false, output = ""): string {
    let seen = "";  // 今の文脈（コンパクションのあとと、今の枝）に残る、前に出したもの。出し直さない
    if (!nested) {  // 入れ子の呼び出し（ctx.executeTool。id は <親>/<n>）の結果は呼んだ道具にしか渡らないので、毎回出す
      seen = turn;
      try {
        seen += "\n" + ctx.sessionManager.buildSessionProjection().messages  // モデルに見えるもの（context_edit で外したものは除く）
          .filter((m: any) => m.role === "toolResult" || (m.role === "custom" && m.customType === TYPE))
          .flatMap((m: any) => (typeof m.content === "string" ? [{ text: m.content }] : m.content ?? [])).map((c: any) => String(c.text ?? "")).filter((t: string) => PART.test(t)).join("\n");
      } catch {}
    }
    const r = spawnSync("python3", [SCRIPT, "pi"], { input: JSON.stringify({ cwd: ctx.cwd ?? process.cwd(), text, isPath, seen, output }), encoding: "utf8", timeout: 5000 });
    let context = "";
    try { context = JSON.parse(r.stdout || "{}").context ?? ""; } catch {}
    if (!nested) turn += "\n" + context;
    return context;
  }

  pi.on("turn_start", () => { turn = ""; });  // 前のターンの結果は、もう文脈に載っている
  pi.on("before_agent_start", (ev: any, ctx: any) => {  // /skill:<名前> で呼んだスキルは、読む道具を通らずに SKILL.md が入る（<skill name=… location=…> に広げてから呼ばれる）
    turn = "";  // 新しい実行の頭（止めた実行の残りは、その前のコンパクションで消えていることがある）
    const m = /^<skill name="[^"]+" location="([^"]+)">/.exec(String(ev.prompt ?? ""));
    const context = m ? overlay(ctx, m[1], true) : "";
    if (context) return { message: { customType: TYPE, content: context, display: false } };
  });
  pi.on("tool_result", (ev: any, ctx: any) => {
    if (ev.isError || !["read", "bash"].includes(ev.toolName)) return;
    const text = String(ev.input?.path ?? ev.input?.command ?? "");
    if (!text.includes(".md")) return;  // 足すのは .md を読んだときだけ（hooks.json の if と同じ）。ほかの呼び出しでは文脈をたどらず、python3 も起こさない
    const output = ev.toolName === "bash" ? (ev.content ?? []).map((c: any) => String(c.text ?? "")).join("\n") : "";  // 名前だけで開いたときも、出た中身でプラグインのファイルが分かる（read はパスで見る。Claude Code の Read と同じ）
    const context = overlay(ctx, text, ev.toolName === "read", String(ev.toolCallId ?? "").includes("/"), output);
    if (context) return { content: [...ev.content, { type: "text", text: "\n\n" + context }] };
  });
}
