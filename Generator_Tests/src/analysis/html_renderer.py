# ===== FILE: C:\Diplom\bsc_Muravin\Generator_Tests\src\analysis\html_renderer.py =====

import html as _html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.analysis.report_generator import AnalysisReport


def _e(v) -> str:
    return "" if v is None else _html.escape(str(v))


_CSS = r"""
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:      #f1f5f9;
  --surface: #ffffff;
  --border:  #e2e8f0;
  --text:    #1e293b;
  --muted:   #64748b;
  --radius:  14px;
  --shadow:  0 1px 3px #0000000a, 0 8px 24px #00000008;
  --green:   #059669;
  --yellow:  #ca8a04;
  --red:     #dc2626;
  --blue:    #2563eb;
  --indigo:  #4f46e5;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.65;
}
a { color: var(--blue); text-decoration: none; }
a:hover { text-decoration: underline; }
code, pre {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.wrap { max-width: 1060px; margin: 0 auto; padding: 32px 16px 80px; }

/* ── page header ── */
.page-header {
  background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
  color: #fff; border-radius: var(--radius);
  padding: 32px 40px; margin-bottom: 32px;
}
.page-header h1 { font-size: 1.6rem; font-weight: 700; margin-bottom: 6px; }
.page-header .meta { font-size: .85rem; opacity: .6; }
.page-header .meta span { margin-right: 20px; }

/* ── card ── */
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 28px 32px;
  margin-bottom: 24px; box-shadow: var(--shadow);
}
.card-title {
  display: flex; align-items: center; gap: 12px; margin-bottom: 20px;
}
.card-title h2 { font-size: 1.15rem; font-weight: 700; }
.card-title .icon { font-size: 1.5rem; }

/* ── metrics ── */
.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px; margin-bottom: 24px;
}
.metric {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px 18px;
}
.metric .val {
  font-size: 1.9rem; font-weight: 800; line-height: 1; margin-bottom: 4px;
}
.metric .lbl { font-size: .78rem; color: var(--muted); }
.metric.green  .val { color: var(--green); }
.metric.yellow .val { color: var(--yellow); }
.metric.red    .val { color: var(--red); }
.metric.blue   .val { color: var(--blue); }
.metric.neutral .val { color: var(--text); }

/* ── coverage single bar ── */
.cov-total-bar {
  height: 12px; border-radius: 20px;
  background: #e2e8f0; overflow: hidden; margin-bottom: 8px;
}
.cov-total-bar-fill { height: 100%; border-radius: 20px; transition: width .4s; }
.cov-total-label {
  font-size: .8rem; color: var(--muted); margin-bottom: 20px;
}

/* ── duplication pairs ── */
.dup-list { display: flex; flex-direction: column; gap: 8px; }
.dup-item {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 12px 16px;
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 8px;
}
.dup-names { font-size: .875rem; }
.dup-names code {
  background: rgba(0,0,0,.05); padding: 1px 6px; border-radius: 4px;
  font-size: .82rem;
}
.dup-sim {
  font-size: .8rem; font-weight: 700; padding: 3px 10px;
  border-radius: 20px;
}
.dup-exact { background: #fef2f2; color: var(--red); }
.dup-near  { background: #fefce8; color: var(--yellow); }
.no-dups {
  text-align: center; padding: 24px; color: var(--muted); font-size: .9rem;
}

/* ── mutation tabs ── */
.mut-tabs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }
.mut-tab {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 14px; border: 1px solid var(--border);
  border-radius: 20px; cursor: pointer; font-size: .82rem;
  background: var(--surface); transition: all .15s; font-family: inherit;
}
.mut-tab:hover { border-color: var(--indigo); color: var(--indigo); }
.mut-tab.active { background: #1e293b; color: #fff; border-color: #1e293b; }
.mut-panel { display: none; }
.mut-panel.active { display: block; }

/* ── main tabs (new) ── */
.main-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0;
}
.main-tab {
  padding: 10px 24px;
  font-size: 0.9rem;
  font-weight: 600;
  background: transparent;
  border: none;
  border-radius: 30px 30px 0 0;
  cursor: pointer;
  color: var(--muted);
}
.main-tab:hover {
  color: var(--indigo);
  background: #eef2ff;
}
.main-tab.active {
  color: var(--indigo);
  background: #eef2ff;
  border-bottom: 2px solid var(--indigo);
}
.tab-panel {
  display: none;
}
.tab-panel.active {
  display: block;
}

/* ── mutation search ── */
.mut-search {
  margin: 16px 0 12px 0;
}
.mut-search input {
  width: 100%;
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: 40px;
  font-size: 0.85rem;
  background: var(--surface);
}
.mut-search input:focus {
  outline: none;
  border-color: var(--indigo);
}
.mut-tab.hidden {
  display: none;
}
.mut-panel.hidden {
  display: none;
}

/* rest of existing styles ... */
.func-header {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 10px;
  background: var(--bg); border-radius: 10px;
  padding: 12px 16px; margin-bottom: 12px;
}
.func-name { font-weight: 700; font-size: .95rem; }
.func-badges { display: flex; gap: 8px; flex-wrap: wrap; }
.badge {
  padding: 3px 10px; border-radius: 20px;
  font-size: .75rem; font-weight: 700;
}
.badge-green { background: #f0fdf4; color: var(--green); }
.badge-red   { background: #fef2f2; color: var(--red); }
.badge-muted { background: var(--bg); color: var(--muted);
               border: 1px solid var(--border); }

/* mutant cards */
.mutants { display: flex; flex-direction: column; gap: 6px; }
.mutant {
  border: 1px solid var(--border); border-left-width: 4px;
  border-radius: 8px; overflow: hidden;
}
.mutant summary {
  display: flex; align-items: center; justify-content: space-between;
  padding: 9px 14px; cursor: pointer; list-style: none; font-size: .85rem;
}
.mutant summary::-webkit-details-marker { display: none; }
.mutant-left { display: flex; align-items: center; gap: 10px; }
.mutant-id   { color: var(--muted); font-family: monospace; font-size: .78rem; }
.mutant-type {
  background: rgba(0,0,0,.05); border-radius: 4px;
  padding: 1px 7px; font-size: .76rem;
}
.mutant-ln { font-size: .76rem; color: var(--muted); }
.mutant-body { padding: 10px 14px; border-top: 1px solid rgba(0,0,0,.06); }
.mutant-desc { font-size: .8rem; color: var(--muted); margin-bottom: 8px; }

/* diff */
.diff { border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
.diff-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 5px 12px; background: #f8fafc; font-size: .76rem;
}
.diff-legend { display: flex; gap: 10px; }
.diff-legend .r { color: var(--red); }
.diff-legend .g { color: var(--green); }
.diff-code { font-size: .79rem; }
.diff-line {
  display: grid; grid-template-columns: 36px 14px 1fr; padding: 1px 0;
}
.diff-ln   { text-align: right; padding-right: 6px; color: #94a3b8; user-select: none; }
.diff-sign { color: #94a3b8; user-select: none; }
.diff-ct   { padding-left: 4px; white-space: pre-wrap; }
.dl-removed { background: #fef2f2; }
.dl-removed .diff-sign { color: var(--red); }
.dl-removed .diff-ct   { color: #7f1d1d; }
.dl-added { background: #f0fdf4; }
.dl-added .diff-sign { color: var(--green); }
.dl-added .diff-ct   { color: #14532d; }
.dl-ctx  { background: #fff; }
.dl-hunk { background: #eff6ff; }
.dl-hunk .diff-ct { color: #1d4ed8; }

/* ── reliability ── */
.runs-grid { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.run-chip {
  padding: 4px 12px; border-radius: 20px; font-size: .8rem; font-weight: 600;
}
.run-pass { background: #f0fdf4; color: var(--green); }
.run-fail { background: #fef2f2; color: var(--red); }
.flaky-list { margin-top: 14px; display: flex; flex-direction: column; gap: 6px; }
.flaky-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; background: #fef9c3; border: 1px solid #fde047;
  border-radius: 8px; font-size: .85rem;
}

/* coverage link */
.cov-link {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 9px 18px; background: var(--blue); color: #fff;
  border-radius: 8px; font-weight: 600; font-size: .875rem; margin-top: 16px;
}
.cov-link:hover { background: #1d4ed8; text-decoration: none; }

.no-data { text-align: center; color: var(--muted); padding: 32px; font-size: .9rem; }

@media (max-width: 600px) {
  .metrics { grid-template-columns: 1fr 1fr; }
  .llm-ex-grid { grid-template-columns: 1fr; }
  .page-header { padding: 24px 20px; }
  .card { padding: 20px; }
}


/* ===== COVERAGE TREE ===== */
.coverage-tree {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--rs);
  padding: 12px;
}

.cov-folder {
  margin-bottom: 4px;
  border-left: 2px solid var(--border);
  margin-left: 0;
}

.cov-folder-level-0 {
  border-left: none;
  border: 1px solid var(--border);
  border-radius: var(--rs);
  margin-bottom: 8px;
}

.cov-folder-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg3);
  cursor: pointer;
  list-style: none;
  user-select: none;
  font-weight: 600;
  font-size: 0.9rem;
  transition: background 0.2s;
  border-radius: 6px;
}

.cov-folder-level-0 > .cov-folder-header {
  background: var(--surface);
  padding: 10px 14px;
}

.cov-folder-header::-webkit-details-marker {
  display: none;
}

.cov-folder-header::marker {
  display: none;
}

.cov-folder-header::before {
  content: '▶';
  font-size: 0.7rem;
  color: var(--muted);
  transition: transform 0.2s;
  display: inline-block;
}

.cov-folder[open] > .cov-folder-header::before {
  transform: rotate(90deg);
}

.cov-folder-header:hover {
  background: var(--surface);
}

.cov-folder-level-0 > .cov-folder-header:hover {
  background: var(--bg3);
}

.cov-folder-icon {
  font-size: 1rem;
}

.cov-folder-name {
  flex: 1;
  color: var(--text);
  font-family: var(--mono);
  font-size: 0.85rem;
}

.cov-folder-stats {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cov-folder-content {
  padding: 4px 8px 4px 20px;
}

.cov-folder-level-0 > .cov-folder-content {
  padding: 8px 12px 12px 12px;
  background: var(--bg);
}

.cov-files-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
  margin-bottom: 8px;
}

.cov-file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--surface);
  transition: background 0.15s;
}

.cov-file-item:hover {
  background: var(--bg3);
}

.cov-file-icon {
  font-size: 0.9rem;
  flex-shrink: 0;
}

.cov-file-name {
  flex: 1;
  font-family: var(--mono);
  font-size: 0.85rem;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cov-file-percent {
  font-size: 0.85rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  min-width: 50px;
  text-align: center;
  flex-shrink: 0;
}

.cov-file-link {
  color: var(--blue);
  text-decoration: none;
  font-size: 0.8rem;
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid var(--border);
  transition: all 0.15s;
  flex-shrink: 0;
}

.cov-file-link:hover {
  background: var(--blue);
  color: white;
  border-color: var(--blue);
  text-decoration: none;
}

@media (max-width: 600px) {
  .cov-folder-content {
    padding-left: 12px;
  }
  
  .cov-file-item {
    flex-wrap: wrap;
  }
  
  .cov-file-name {
    width: 100%;
    margin-bottom: 4px;
  }
}
</style>
"""

_JS = r"""
<script>
// Main tab switching
function switchMainTab(tabId) {
    document.querySelectorAll('.main-tab').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
    document.getElementById('panel-' + tabId).classList.add('active');
    document.getElementById('tab-' + tabId).classList.add('active');
}

// Mutation per‑function tabs (original)
function mutTab(btn, panelId) {
    const root = btn.closest('.mut-root');
    root.querySelectorAll('.mut-tab').forEach(t => t.classList.remove('active'));
    root.querySelectorAll('.mut-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(panelId).classList.add('active');
}

function filterMutationFunctions() {
    const input = document.getElementById('mutSearchInput');
    const filter = input.value.toLowerCase().trim();
    const root = document.querySelector('.mut-root');
    if (!root) return;
    const tabs = root.querySelectorAll('.mut-tab');
    const panels = root.querySelectorAll('.mut-panel');
    let firstVisible = null;
    tabs.forEach((tab, idx) => {
        const text = tab.textContent.toLowerCase();
        const matches = filter === '' || text.includes(filter);
        if (matches) {
            tab.classList.remove('hidden');
            if (firstVisible === null) firstVisible = idx;
        } else {
            tab.classList.add('hidden');
        }
    });
    panels.forEach((panel, idx) => {
        const tab = tabs[idx];
        if (tab && !tab.classList.contains('hidden')) {
            panel.classList.remove('hidden');
        } else {
            panel.classList.add('hidden');
        }
    });
    const activeTab = root.querySelector('.mut-tab.active');
    if (activeTab && activeTab.classList.contains('hidden')) {
        if (firstVisible !== null) {
            const firstTab = tabs[firstVisible];
            const match = firstTab.getAttribute('onclick').match(/'(mpanel-\d+)'/);
            if (match) mutTab(firstTab, match[1]);
        }
    }
}

</script>
"""


def _pct_cls(pct: float) -> str:
    if pct >= 80:
        return "green"
    if pct >= 60:
        return "yellow"
    return "red"


def _pct_color(pct: float) -> str:
    return {"green": "#059669", "yellow": "#ca8a04", "red": "#dc2626"}[_pct_cls(pct)]


def _metric(val: str, lbl: str, cls: str = "neutral") -> str:
    return f'<div class="metric {cls}"><div class="val">{_e(val)}</div><div class="lbl">{_e(lbl)}</div></div>'


def _coverage_card(r: "AnalysisReport") -> str:
    v = r.verdicts.get("coverage")
    if not v:
        return ""

    meta = v.metadata
    total = meta.get("total_coverage_percent", 0.0)
    stmts = meta.get("total_statements", 0)
    miss = meta.get("total_missing", 0)
    covered = stmts - miss
    cls = _pct_cls(total)
    color = _pct_color(total)

    metrics_html = (
        _metric(f"{total:.1f}%", "Total Coverage", cls)
        + _metric(str(stmts), "Statements", "neutral")
        + _metric(str(covered), "Covered", "green")
        + _metric(str(miss), "Missing", "red" if miss > 0 else "green")
    )

    bar_html = f"""
<div class="cov-total-bar">
  <div class="cov-total-bar-fill" style="width:{total:.1f}%;background:{color}"></div>
</div>
<div class="cov-total-label">{covered} of {stmts} statements covered</div>"""

    link_html = ""
    if r.coverage_html_path:
        link_html = f'<a href="{_e(r.coverage_html_path)}" class="cov-link" target="_blank">📊 Open Detailed Coverage Report</a>'

    annotate_stats = getattr(r, "coverage_annotate_stats", {})
    annotate_html = ""

    if annotate_stats:
        # ✅ Строим дерево папок
        tree_html = _build_coverage_tree(annotate_stats, r.coverage_annotate_path)

        annotate_html = f"""
        <div style="margin-top: 24px;">
            <h3 style="font-size:1rem; margin-bottom:12px;">📂 Annotated source files</h3>
            <div class="coverage-tree">
                {tree_html}
            </div>
            <div style="margin-top:12px; font-size:0.8rem; color:var(--muted);">
                💡 Annotated files show covered lines with <code>&gt;</code> and missing lines with <code>!</code>.
            </div>
        </div>
        """

    return f"""
<div class="card">
  <div class="card-title"><span class="icon">📊</span><h2>Coverage</h2></div>
  <div class="metrics">{metrics_html}</div>
  {bar_html}
  <div style="display: flex; gap: 12px; flex-wrap: wrap;">
    {link_html}
  </div>
  {annotate_html}
</div>"""


def _build_coverage_tree(annotate_stats: dict, base_path: str) -> str:
    """Строит рекурсивную древовидную структуру файлов по папкам."""
    from pathlib import Path

    # Строим дерево: путь → {folders, files}
    def build_tree_structure(stats):
        root = {"folders": {}, "files": []}

        for name, info in stats.items():
            original_path = Path(info["original_path"])
            parts = list(original_path.parts)

            # Навигируемся по дереву, создавая папки по пути
            current = root
            for part in parts[:-1]:  # Все части кроме имени файла
                if part not in current["folders"]:
                    current["folders"][part] = {"folders": {}, "files": []}
                current = current["folders"][part]

            # Добавляем файл в конечную папку
            current["files"].append(
                {
                    "name": original_path.name,
                    "full_path": info["original_path"],
                    "percent": info["percent"],
                    "cover_file": info["cover_file"],
                }
            )

        return root

    tree = build_tree_structure(annotate_stats)

    # Если в корне только папки и нет файлов, рендерим их напрямую
    if not tree["files"] and tree["folders"]:
        return _render_tree_level(tree["folders"], base_path, level=0)
    else:
        # Если в корне есть файлы, оборачиваем всё в корневую папку
        return _render_tree_level({"root": tree}, base_path, level=0)


def _render_tree_level(folders: dict, base_path: str, level: int = 0) -> str:
    """Рендерит один уровень дерева (папки и файлы)."""
    html = ""

    for folder_name, content in sorted(folders.items()):
        subfolders = content.get("folders", {})
        files = content.get("files", [])

        # Вычисляем средний процент покрытия рекурсивно
        all_percents = _collect_all_percents(content)
        avg_percent = sum(all_percents) / len(all_percents) if all_percents else 0
        folder_cls = _pct_cls(avg_percent)

        # Считаем общее количество файлов
        total_files = _count_all_files(content)

        # Иконка папки
        folder_icon = "📁" if level == 0 else "📂"

        # Атрибут open только для первого уровня
        open_attr = "open" if level == 0 else ""

        html += f"""
<details class="cov-folder cov-folder-level-{level}" {open_attr}>
  <summary class="cov-folder-header">
    <span class="cov-folder-icon">{folder_icon}</span>
    <span class="cov-folder-name">{_e(folder_name)}</span>
    <span class="cov-folder-stats">
      <span class="metric {folder_cls}" style="font-size:0.85rem; padding:2px 8px;">
        {avg_percent:.1f}%
      </span>
      <span style="color:var(--muted); font-size:0.8rem;">
        {total_files} file{'s' if total_files != 1 else ''}
      </span>
    </span>
  </summary>
  <div class="cov-folder-content">
"""

        # Сначала рендерим вложенные папки
        if subfolders:
            html += _render_tree_level(subfolders, base_path, level + 1)

        # Затем файлы в текущей папке
        if files:
            html += '    <div class="cov-files-list">\n'
            for file_info in sorted(files, key=lambda x: x["name"]):
                percent = file_info["percent"]
                file_cls = _pct_cls(percent)
                annotate_url = f"{base_path}/{file_info['cover_file']}"

                html += f"""
      <div class="cov-file-item">
        <span class="cov-file-icon">📄</span>
        <span class="cov-file-name">{_e(file_info['name'])}</span>
        <span class="cov-file-percent metric {file_cls}">{percent:.1f}%</span>
        <a href="{_e(annotate_url)}" class="cov-file-link" target="_blank">view</a>
      </div>
"""
            html += "    </div>\n"

        html += """
  </div>
</details>
"""

    return html


def _collect_all_percents(node: dict) -> list[float]:
    """Рекурсивно собирает все проценты из узла дерева."""
    percents = []

    # Проценты из файлов текущей папки
    for file_info in node.get("files", []):
        percents.append(file_info["percent"])

    # Рекурсивно из вложенных папок
    for subfolder in node.get("folders", {}).values():
        percents.extend(_collect_all_percents(subfolder))

    return percents


def _count_all_files(node: dict) -> int:
    """Рекурсивно считает количество файлов в узле дерева."""
    count = len(node.get("files", []))

    for subfolder in node.get("folders", {}).values():
        count += _count_all_files(subfolder)

    return count


def _duplication_card(r: "AnalysisReport") -> str:

    v = r.verdicts.get("duplication")
    if not v:
        return ""
    meta = v.metadata
    total = meta.get("total_tests", 0)
    near = meta.get("near_duplicates", 0)
    pairs = meta.get("duplicate_pairs", [])
    metrics_html = _metric(str(total), "Tests Analyzed", "neutral") + _metric(
        str(near), "Near Duplicates", "yellow" if near > 0 else "green"
    )
    pairs_html = ""
    if pairs:
        items = ""
        for p in pairs:
            t1 = p.get("test1", "")
            t2 = p.get("test2", "")
            sim = p.get("similarity", 0.0)
            is_exact = sim >= 0.98
            sim_cls = "dup-exact" if is_exact else "dup-near"
            sim_lbl = f"{'Exact' if is_exact else 'Similar'} {sim:.0%}"
            items += f"""
<div class="dup-item">
  <div class="dup-names">
    <code>{_e(t1)}</code>
    <span style="margin:0 8px;color:var(--muted)">↔</span>
    <code>{_e(t2)}</code>
  </div>
  <span class="dup-sim {sim_cls}">{_e(sim_lbl)}</span>
</div>"""
        pairs_html = f'<div class="dup-list">{items}</div>'
    else:
        pairs_html = '<div class="no-dups">✨ No duplicate tests found</div>'
    return f"""
<div class="card">
  <div class="card-title"><span class="icon">📋</span><h2>Duplication</h2></div>
  <div class="metrics">{metrics_html}</div>
  {pairs_html}
</div>"""


def _mutation_card(r: "AnalysisReport") -> str:
    v = r.verdicts.get("mutation")
    if not v:
        return ""
    meta = v.metadata
    total_m = meta.get("total_mutants", 0)
    killed = meta.get("total_killed", 0)
    survived = meta.get("total_survived", 0)
    funcs = meta.get("functions_tested", 0)
    dur = meta.get("duration_seconds", 0)
    score = killed / total_m * 100 if total_m else 100.0
    cls = _pct_cls(score)
    metrics_html = (
        _metric(f"{score:.1f}%", "Kill Rate", cls)
        + _metric(str(total_m), "Mutants", "neutral")
        + _metric(str(killed), "Killed ✅", "green")
        + _metric(str(survived), "Survived ❌", "red" if survived > 0 else "green")
        + _metric(str(funcs), "Functions", "neutral")
        + _metric(f"{dur:.1f}s", "Duration", "neutral")
    )
    mut_detail = _mutation_detail_tabs(r)
    return f"""
<div class="card">
  <div class="card-title"><span class="icon">🧬</span><h2>Mutation Testing</h2></div>
  <div class="metrics">{metrics_html}</div>
  {mut_detail}
</div>"""


def _mutation_detail_tabs(r: "AnalysisReport") -> str:
    if not r.mutation_results:
        return ""
    search_html = """
<div class="mut-search">
  <input type="text" id="mutSearchInput" placeholder="🔍 Filter by function name..." oninput="filterMutationFunctions()">
</div>"""
    tabs = ""
    panels = ""
    for idx, (fn, res) in enumerate(r.mutation_results.items()):
        active = "active" if idx == 0 else ""
        short = fn.split(".")[-1] if "." in fn else fn
        dot = "🟢" if res.score >= 80 else "🟡" if res.score >= 60 else "🔴"
        tabs += f"""
<button class="mut-tab {active}" onclick="mutTab(this,'mpanel-{idx}')">
  {dot} {_e(short)} <strong>{res.score:.0f}%</strong>
</button>"""
        panels += _mut_panel(idx, fn, res, active)
    return f"""
<div class="mut-root" style="margin-top:4px">
  <div style="font-size:.78rem;color:var(--muted);margin-bottom:8px;font-weight:600;text-transform:uppercase;letter-spacing:.05em">
    Per-function details
  </div>
  {search_html}
  <div class="mut-tabs">{tabs}</div>
  {panels}
</div>"""


def _mut_panel(idx: int, fn: str, res, active: str) -> str:
    color = _pct_color(res.score)
    cards = "".join((_mutant_card(m) for m in sorted(res.mutants, key=lambda m: (m.killed, m.id))))
    return f"""
<div class="mut-panel {active}" id="mpanel-{idx}">
  <div class="func-header">
    <span class="func-name">⚡ {_e(fn)}</span>
    <div class="func-badges">
      <span class="badge badge-green">✅ {res.killed} killed</span>
      <span class="badge badge-red">❌ {res.survived} survived</span>
      <span class="badge badge-muted" style="color:{color}">{res.score:.1f}%</span>
    </div>
  </div>
  <div class="mutants">{cards}</div>
</div>"""


def _mutant_card(m) -> str:
    if m.killed:
        border = "#10b981"
        bg = "#05966908"
        badge_cls = "badge-green"
        status = "KILLED"
    elif m.survived:
        border = "#ef4444"
        bg = "#ef444408"
        badge_cls = "badge-red"
        status = "SURVIVED"
    else:
        border = "#94a3b8"
        bg = "#94a3b808"
        badge_cls = "badge-muted"
        status = "TIMEOUT"
    icons = {
        "comparison_swap": "⚖️",
        "boolean_swap": "🔀",
        "arithmetic_swap": "➕",
        "return_none": "↩️",
        "negate_condition": "🔄",
        "constant_swap": "🔢",
    }
    ticon = icons.get(m.mutation_type.value, "🔧")
    tlabel = m.mutation_type.value.replace("_", " ").title()
    diff = _render_diff(m.get_diff_lines(context_lines=2))
    return f"""
<details class="mutant" style="border-color:{border};background:{bg}">
  <summary>
    <div class="mutant-left">
      <span class="mutant-id">#{m.id}</span>
      <span class="mutant-type">{ticon} {_e(tlabel)}</span>
      <span class="mutant-ln">line {m.line_number}</span>
    </div>
    <span class="badge {badge_cls}">{status}</span>
  </summary>
  <div class="mutant-body">
    <div class="mutant-desc">{_e(m.description)}</div>
    <div class="diff">
      <div class="diff-head">
        <span>Code Change</span>
        <span class="diff-legend">
          <span class="r">− original</span>
          <span class="g">+ mutant</span>
        </span>
      </div>
      <div class="diff-code">{diff}</div>
    </div>
  </div>
</details>"""


def _render_diff(diff_lines: list[dict]) -> str:
    if not diff_lines:
        return '<div class="no-data">No diff</div>'
    out = ""
    for dl in diff_lines:
        t = dl["type"]
        ln = dl.get("line_no", "")
        ct = _e(dl.get("content", ""))
        if t == "header":
            out += f'<div class="diff-line dl-hunk"><span class="diff-ln"></span><span class="diff-sign"> </span><span class="diff-ct">{ct}</span></div>'
        elif t == "removed":
            out += f'<div class="diff-line dl-removed"><span class="diff-ln">{ln}</span><span class="diff-sign">−</span><span class="diff-ct">{ct}</span></div>'
        elif t == "added":
            out += f'<div class="diff-line dl-added"><span class="diff-ln">{ln}</span><span class="diff-sign">+</span><span class="diff-ct">{ct}</span></div>'
        else:
            out += f'<div class="diff-line dl-ctx"><span class="diff-ln">{ln}</span><span class="diff-sign"> </span><span class="diff-ct">{ct}</span></div>'
    return out


def _reliability_card(r: "AnalysisReport") -> str:
    v = r.verdicts.get("reliability")
    if not v:
        return ""
    meta = v.metadata
    num_runs = meta.get("num_runs", 0)
    all_pass = meta.get("all_pass_runs", 0)
    all_fail = meta.get("all_fail_runs", 0)
    flaky_list = meta.get("flaky_tests", [])
    flaky_cnt = meta.get("flaky_count", 0)
    chips = ""
    for i in range(num_runs):
        if i < all_pass:
            chips += '<span class="run-chip run-pass">Run passed ✅</span>'
        else:
            chips += '<span class="run-chip run-fail">Run failed ❌</span>'
    metrics_html = (
        _metric(str(num_runs), "Total Runs", "neutral")
        + _metric(str(all_pass), "Passed", "green" if all_pass == num_runs else "yellow")
        + _metric(str(all_fail), "Failed", "red" if all_fail > 0 else "green")
        + _metric(str(flaky_cnt), "Flaky", "red" if flaky_cnt > 0 else "green")
    )
    flaky_html = ""
    if flaky_list:
        items = "".join(
            (f'<div class="flaky-item">⚠️ <code>{_e(t)}</code></div>' for t in flaky_list)
        )
        flaky_html = f'<div class="flaky-list">{items}</div>'
    return f"""
<div class="card">
  <div class="card-title"><span class="icon">⚡</span><h2>Reliability</h2></div>
  <div class="metrics">{metrics_html}</div>
  <div class="runs-grid">{chips}</div>
  {flaky_html}
</div>"""


def build_html(report: "AnalysisReport") -> str:
    header = f"""
<div class="page-header">
  <h1>🔬 Test Analysis Report</h1>
  <div class="meta">
    <span>📁 {_e(report.project_root)}</span>
    <span>🕐 {_e(report.timestamp)}</span>
  </div>
</div>"""

    # Main tabs with IDs for highlighting
    tabs_html = """
<div class="main-tabs">
  <button id="tab-coverage" class="main-tab active" onclick="switchMainTab('coverage')">📊 Coverage</button>
  <button id="tab-duplication" class="main-tab" onclick="switchMainTab('duplication')">📋 Duplication</button>
  <button id="tab-mutation" class="main-tab" onclick="switchMainTab('mutation')">🧬 Mutation</button>
  <button id="tab-reliability" class="main-tab" onclick="switchMainTab('reliability')">⚡ Reliability</button>
</div>"""

    panels_html = f"""
<div id="panel-coverage" class="tab-panel active">{_coverage_card(report)}</div>
<div id="panel-duplication" class="tab-panel">{_duplication_card(report)}</div>
<div id="panel-mutation" class="tab-panel">{_mutation_card(report)}</div>
<div id="panel-reliability" class="tab-panel">{_reliability_card(report)}</div>"""

    body = header + tabs_html + panels_html
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Test Analysis Report</title>
  {_CSS}
</head>
<body>
<div class="wrap">
  {body}
</div>
{_JS}
</body>
</html>"""
