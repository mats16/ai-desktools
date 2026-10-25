// pi の側のつなぎ: read・bash の結果に、ワークスペースの rules/ の同じパスのファイルと、顧客の memory.md を足す（今の文脈に残るものは足さない）。中身は hooks/rules_overlay.py（Claude Code と共有）
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = join(dirname(fileURLToPath(import.meta.url)), "..", "hooks", "rules_overlay.py");

export default function (pi: any) {
  pi.on("tool_result", (ev: any, ctx: any) => {
    if (ev.isError || !["read", "bash"].includes(ev.toolName)) return;
    const text = String(ev.input?.path ?? ev.input?.command ?? "");
    let seen = "";  // 今の文脈（コンパクションのあとと、今の枝）に残る、前に出したもの。出し直さない
    if (!String(ev.toolCallId ?? "").includes("/")) try {  // 入れ子の呼び出し（ctx.executeTool。id は <親>/<n>）の結果は呼んだ道具にしか渡らないので、毎回出す
      seen = ctx.sessionManager.buildSessionProjection().messages.filter((m: any) => m.role === "toolResult")  // モデルに見えるもの（context_edit で外したものは除く）
        .flatMap((m: any) => m.content ?? []).map((c: any) => String(c.text ?? "")).filter((t: string) => t.includes("\n## ワークスペースの決まり: ") || t.includes("\n## 顧客の memory: ")).join("\n");
    } catch {}
    const r = spawnSync("python3", [SCRIPT, "pi"], { input: JSON.stringify({ cwd: ctx.cwd ?? process.cwd(), text, isPath: ev.toolName === "read", seen }), encoding: "utf8", timeout: 5000 });
    let context = "";
    try { context = JSON.parse(r.stdout || "{}").context ?? ""; } catch { return; }
    if (context) return { content: [...ev.content, { type: "text", text: "\n\n" + context }] };
  });
}
