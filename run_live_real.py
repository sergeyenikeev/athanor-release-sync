# -*- coding: utf-8 -*-
"""Реальный live-прогон athanor через MCP на данных из реальных облаков.

Поднимает 4 MCP-сервера в потоках с MCP_BACKEND=live MCP_BACKEND_PR=bitbucket
(Jira+Confluence Cloud, Bitbucket Cloud, Google mail+Calendar — реальные),
прогоняет athanor на кейсе examples/demo_case_alpha_live через --via-mcp,
сохраняет честный артефакт в results/runs/live_real_<timestamp>/.

Это НЕ «реальный прогон Ouroboros v6.64» (task dec66d75, GUI) — это athanor CLI
+ MCP на live-данных. Честно обозначено в run.json.run_kind = "live-mcp-athanor".
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

import codecs
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")
sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "replace")

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "mcp"))

# .env
for line in (REPO / ".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

os.environ["MCP_CASE_DIR"] = "examples/demo_case_alpha_live"
os.environ["MCP_BACKEND"] = "live"
os.environ["MCP_BACKEND_PR"] = "bitbucket"

import calendar_mail, tracker_repo, transcripts, confluence  # noqa: E402
from _base import serve  # noqa: E402

from athanor.agent import run_case  # noqa: E402
from athanor.config import load_config  # noqa: E402
from athanor.format import render_result  # noqa: E402
from athanor.skill_versioning import get_active_version  # noqa: E402
from athanor.sources import load_case_via_mcp  # noqa: E402


def _prepare_memory(case_dir: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="athanor-mem-"))
    (tmp / "knowledge").mkdir(parents=True, exist_ok=True)
    ident = REPO / "memory" / "identity.md"
    if ident.is_file():
        shutil.copy(ident, tmp / "identity.md")
    seed = case_dir / "input" / "memory_seed.md"
    if seed.is_file():
        shutil.copy(seed, tmp / "knowledge" / "release_alfa.md")
    return tmp


def main() -> int:
    print("=== Live-прогон athanor через MCP на реальных данных облаков ===")
    print(f"MCP_BACKEND={os.environ['MCP_BACKEND']}  MCP_BACKEND_PR={os.environ['MCP_BACKEND_PR']}")
    print(f"MCP_CASE_DIR={os.environ['MCP_CASE_DIR']}\n")

    # 1) MCP-серверы в потоках
    servers = []
    for mod, port in [(calendar_mail, 9901), (tracker_repo, 9902),
                      (transcripts, 9903), (confluence, 9904)]:
        srv = serve(mod.server, port)
        servers.append(srv)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"  MCP {mod.server.name:<14} http://127.0.0.1:{port}/mcp")
    time.sleep(2.5)
    print()

    try:
        cfg = load_config()
        case_dir = REPO / "examples" / "demo_case_alpha_live"
        meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
        fmt = meta.get("format", "v1")
        print("Сбор данных через MCP (live)...")
        case = load_case_via_mcp(cfg, case_dir.name)
        print(f"  event: {case.event.title if case.event else None} @ {case.event.datetime if case.event else None}")
        print(f"  issues: {[(i.key, i.status) for i in case.issues]}")
        print(f"  prs: {[(p.number, p.title, p.issue_key) for p in case.prs]}")
        print(f"  mails: {len(case.mails)} ({[m.subject for m in case.mails]})")
        print(f"  confluence: {[(p.title, p.id) for p in case.confluence_pages]}")
        print(f"  transcript: {len(case.transcript) if case.transcript else 0} chars")
        print(f"  sources_down: {case.sources_down}\n")

        memory_dir = _prepare_memory(case_dir)
        run_id = dt.datetime.now().strftime("live_real_%Y%m%dT%H%M%S")
        out_dir = REPO / "results" / "runs" / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        res = run_case(case, case_id=case_dir.name, cfg=cfg, memory_dir=memory_dir,
                       outbox_dir=out_dir / "outbox", engine="rule", format_profile=fmt,
                       skill_version=get_active_version())
        md = render_result(res)
        (out_dir / "output.md").write_text(md, encoding="utf-8")
        run_dict = res.to_dict()
        run_dict["run_kind"] = "live-mcp-athanor"
        run_dict["mcp_backend"] = {"MCP_BACKEND": "live", "MCP_BACKEND_PR": "bitbucket",
                                    "MCP_CASE_DIR": "examples/demo_case_alpha_live"}
        run_dict["engine"] = "rule"
        run_dict["generated_at"] = dt.datetime.now().isoformat(timespec="seconds")
        (out_dir / "run.json").write_text(
            json.dumps(run_dict, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.rmtree(out_dir / "memory_after", ignore_errors=True)
        shutil.copytree(memory_dir, out_dir / "memory_after")

        print("=== output.md ===")
        print(md)
        print(f"\n[saved] {out_dir}")
        return 0
    finally:
        for srv in servers:
            try:
                srv.shutdown()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
