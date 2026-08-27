#!/usr/bin/env python3
"""Render desktop review pages from REQ-first Delivery Proof truth sources."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from req_model import html_escape
from validate_delivery_proof import (
    Project,
    acceptance_eligible_runs,
    artifact_assertion_results,
    artifact_types,
    as_dict,
    as_list,
    load_project,
    predicate_result_passes,
    scenario_proof_state,
    check_proof_state,
)


DEFAULT_ROOT = Path("docs/交付证明")


class ReviewError(ValueError):
    pass


def delivery_stage(project: Project, requirement_id: str) -> tuple[str, str]:
    requirement = as_dict(project.requirements[requirement_id].get("requirement"))
    if requirement.get("status") == "DRAFT":
        return "需求待确认", "warn"
    scenario_doc = project.scenarios.get(requirement_id)
    if scenario_doc is None:
        return "场景未开始", "muted"
    if as_dict(scenario_doc.get("acceptance_scenarios")).get("status") == "DRAFT":
        return "场景待确认", "warn"
    matrix_doc = project.matrices.get(requirement_id)
    if matrix_doc is None:
        return "矩阵未开始", "muted"
    if as_dict(matrix_doc.get("acceptance_matrix")).get("status") == "DRAFT":
        return "矩阵待确认", "warn"
    report = project.reports.get(requirement_id)
    if report is not None:
        status = as_dict(report.get("acceptance_report")).get("status")
        return ("已验收", "ok") if status == "SATISFIED" else ("未通过验收", "bad")
    plan = project.plans.get(requirement_id)
    if plan is None:
        return "开发未开始", "muted"
    plan_status = as_dict(plan.get("implementation_plan")).get("status")
    return {"PLANNED": "实现已规划", "IN_PROGRESS": "开发中", "READY": "待验证"}.get(str(plan_status), str(plan_status)), "info"


def badge(text: Any, kind: str = "info") -> str:
    return f'<span class="badge {kind}">{html_escape(text)}</span>'


def html_page(title: str, body: str, source_digest: str) -> str:
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="delivery-proof-source-sha256" content="{source_digest}">
  <title>{html_escape(title)}</title>
  <style>
    :root {{ --ink:#171b19; --muted:#66706b; --line:#dfe4e1; --paper:#fff; --soft:#f4f6f5; --red:#b42318; --green:#217a4b; --amber:#8a5a00; --blue:#1d4e89; --accent:#2f8f6b; --accent-soft:#eaf8f1; --canvas:#f7f8f7; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-width:0; color:var(--ink); background:var(--canvas); font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif; letter-spacing:0; }}
    a {{ color:var(--blue); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
    button {{ font:inherit; letter-spacing:0; }}
    header {{ border-bottom:1px solid var(--line); background:var(--paper); }}
    .top {{ width:min(1240px,calc(100% - 48px)); margin:0 auto; padding:28px 0 24px; }}
    .eyebrow {{ color:var(--red); font-weight:700; text-transform:uppercase; font-size:12px; }}
    h1 {{ margin:5px 0 8px; font-size:30px; line-height:1.2; letter-spacing:0; }}
    h2 {{ margin:0 0 16px; font-size:20px; letter-spacing:0; }}
    h3 {{ margin:0 0 8px; font-size:15px; letter-spacing:0; }}
    p {{ margin:7px 0; }} .sub,.muted-text {{ color:var(--muted); }}
    main {{ width:min(1240px,calc(100% - 48px)); margin:0 auto; }}
    nav {{ display:flex; gap:20px; height:48px; align-items:center; border-bottom:1px solid var(--line); }}
    section {{ padding:25px 0; border-bottom:1px solid var(--line); }}
    .metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); border:1px solid var(--line); background:var(--paper); }}
    .metric {{ padding:14px 16px; border-right:1px solid var(--line); }} .metric:last-child {{ border-right:0; }}
    .metric strong {{ display:block; font-size:22px; }} .metric span {{ color:var(--muted); font-size:12px; }}
    table {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
    th {{ text-align:left; color:var(--muted); font-size:12px; background:var(--soft); }}
    th,td {{ padding:10px 12px; border:1px solid var(--line); vertical-align:top; overflow-wrap:anywhere; }}
    .badge {{ display:inline-flex; align-items:center; min-height:24px; padding:2px 8px; border:1px solid currentColor; border-radius:4px; font-size:12px; white-space:nowrap; }}
    .badge.ok {{ color:var(--green); background:#f2fbf6; }} .badge.warn {{ color:var(--amber); background:#fff9e9; }}
    .badge.bad {{ color:var(--red); background:#fff4f2; }} .badge.info {{ color:var(--blue); background:#f2f7fc; }} .badge.muted {{ color:var(--muted); background:var(--soft); }}
    .records {{ border-top:1px solid var(--line); }} .record {{ display:grid; grid-template-columns:220px 1fr; gap:20px; padding:15px 0; border-bottom:1px solid var(--line); }}
    .mono {{ font-family:"SFMono-Regular",Consolas,monospace; font-size:12px; }}
    .statement {{ font-size:15px; }} ul {{ margin:7px 0; padding-left:20px; }}
    .split {{ display:grid; grid-template-columns:1fr 1fr; gap:32px; }}
    .scenario-result {{ margin:0 0 14px; padding:13px 15px; border:1px solid #b8cec0; border-left:4px solid var(--green); border-radius:6px; background:#f5faf7; }}
    .scenario-result-label {{ display:block; margin-bottom:4px; color:var(--green); font-size:12px; font-weight:700; }}
    .scenario-result strong {{ display:block; font-size:16px; line-height:1.5; }}
    .scenario-fields {{ display:grid; grid-template-columns:1fr 1fr; column-gap:28px; border-top:1px solid var(--line); }}
    .scenario-field {{ display:grid; grid-template-columns:88px minmax(0,1fr); gap:10px; align-items:start; padding:12px 0; border-bottom:1px solid var(--line); }}
    .scenario-field.action {{ grid-column:1 / -1; }}
    .scenario-field-key {{ color:var(--muted); font-size:12px; font-weight:700; line-height:1.7; }}
    .scenario-field-value {{ min-width:0; margin:0; line-height:1.7; overflow-wrap:anywhere; }}
    .scenario-field-value ul {{ margin:0; padding-left:18px; }}
    .scenario-field-value li + li {{ margin-top:3px; }}
    .implementation-detail {{ margin-top:18px; padding:15px; border:1px solid var(--line); background:var(--paper); }}
    .implementation-detail > summary {{ cursor:pointer; font-weight:700; font-size:15px; }}
    .implementation-detail[open] > summary {{ margin-bottom:14px; }}
    .implementation-slice {{ padding:15px 0; border-top:1px solid var(--line); }}
    .implementation-slice:first-of-type {{ border-top:0; }}
    .slice-heading {{ display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }}
    .slice-heading h3 {{ margin-bottom:0; }}
    .gherkin-outcomes {{ margin:0; padding:0; list-style:none; }}
    .gherkin-outcomes li {{ display:grid; grid-template-columns:94px minmax(0,1fr); gap:10px; padding:4px 0; }}
    .notice {{ padding:12px 14px; border-left:3px solid var(--amber); background:#fff9e9; }}
    .okline {{ padding:12px 14px; border-left:3px solid var(--green); background:#f2fbf6; }}
    .verdict {{ margin:12px 0 4px; padding:12px 14px; border-left:3px solid var(--red); background:#fff4f2; }}
    .verdict.pass {{ border-left-color:var(--green); background:#f2fbf6; }}
    .verdict p:last-child {{ margin-bottom:0; }}
    .chain-check {{ margin:0; padding:18px 0; border:0; border-bottom:1px solid var(--line); background:transparent; }}
    .chain-check:last-child {{ border-bottom:0; }}
    .chain-check h4 {{ margin:0 0 5px; font-size:14px; }}
    .chain-runs {{ margin-top:12px; border-top:1px solid var(--line); }}
    .chain-run {{ padding:10px 0; border-bottom:1px solid var(--line); }}
    .chain-run:last-child {{ border-bottom:0; }}
    .chain-run-head {{ display:flex; flex-wrap:wrap; gap:7px; align-items:center; }}
    .chain-run .mono {{ overflow-wrap:anywhere; }}
    .run-command {{ margin:5px 0 0; color:var(--muted); font-family:"SFMono-Regular",Consolas,monospace; font-size:12px; overflow-wrap:anywhere; }}
    .artifact-links {{ display:inline-flex; flex-wrap:wrap; gap:6px; }}
    .artifact-link {{ font-family:"SFMono-Regular",Consolas,monospace; font-size:12px; }}
    .assertion-coverage {{ margin:10px 0 0; padding:0; list-style:none; border-top:1px solid var(--line); }}
    .assertion-coverage li {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:7px; padding:8px 0; border-bottom:1px solid var(--line); }}
    .assertion-coverage li:last-child {{ border-bottom:0; }}
    .assertion-description {{ flex:1 1 360px; min-width:220px; }}
    .assertion-runs {{ color:var(--muted); font-family:"SFMono-Regular",Consolas,monospace; font-size:12px; }}
    .dependency-checks {{ margin:10px 0 0; padding:0; list-style:none; border-top:1px solid var(--line); }}
    .dependency-checks li {{ display:flex; flex-wrap:wrap; align-items:center; gap:7px; padding:8px 0; border-bottom:1px solid var(--line); }}
    .dependency-checks li:last-child {{ border-bottom:0; }}
    .scenario-browser {{ display:grid; grid-template-columns:290px minmax(0,1fr); min-height:640px; margin-top:18px; border:1px solid var(--line); background:var(--paper); }}
    .scenario-sidebar {{ min-width:0; border-right:1px solid var(--line); background:#fafbfa; }}
    .scenario-nav-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; min-height:56px; padding:14px 16px; border-bottom:1px solid var(--line); }}
    .scenario-nav-head strong {{ font-size:12px; text-transform:uppercase; }}
    .scenario-nav {{ display:flex; flex-direction:column; max-height:720px; overflow:auto; }}
    .scenario-nav-item {{ width:100%; min-height:82px; padding:14px 16px; border:0; border-bottom:1px solid var(--line); color:var(--ink); background:transparent; text-align:left; cursor:pointer; }}
    .scenario-nav-item:hover {{ background:#f1f5f3; }}
    .scenario-nav-item[aria-selected="true"] {{ background:var(--accent-soft); box-shadow:inset 3px 0 0 var(--accent); }}
    .scenario-nav-item:focus-visible,.detail-tab:focus-visible {{ outline:2px solid var(--accent); outline-offset:-2px; }}
    .scenario-nav-line {{ display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:6px; }}
    .scenario-nav-id {{ color:var(--muted); font-family:"SFMono-Regular",Consolas,monospace; font-size:11px; }}
    .scenario-nav-title {{ display:block; font-weight:650; line-height:1.45; overflow-wrap:anywhere; }}
    .scenario-nav-status {{ font-size:11px; font-weight:700; }}
    .scenario-nav-status.pass {{ color:var(--green); }} .scenario-nav-status.blocked,.scenario-nav-status.fail {{ color:var(--red); }} .scenario-nav-status.pending {{ color:var(--muted); }}
    .scenario-detail {{ min-width:0; }}
    .scenario-pane {{ min-width:0; }}
    .scenario-pane[hidden],.scenario-tab-panel[hidden] {{ display:none; }}
    .scenario-pane-header {{ padding:24px 28px 20px; border-bottom:1px solid var(--line); }}
    .scenario-pane-kicker {{ display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-bottom:8px; }}
    .scenario-pane-header h3 {{ margin:0; font-size:23px; line-height:1.3; }}
    .scenario-tabs {{ display:flex; gap:28px; min-height:50px; padding:0 28px; border-bottom:1px solid var(--line); }}
    .detail-tab {{ position:relative; padding:0; border:0; color:var(--muted); background:transparent; font-weight:650; cursor:pointer; }}
    .detail-tab[aria-selected="true"] {{ color:var(--ink); }}
    .detail-tab[aria-selected="true"]::after {{ position:absolute; right:0; bottom:-1px; left:0; height:2px; background:var(--accent); content:""; }}
    .scenario-tab-panel {{ padding:24px 28px 32px; }}
    .scenario-check-summary {{ display:flex; align-items:center; justify-content:space-between; gap:16px; padding-bottom:12px; border-bottom:1px solid var(--line); }}
    .scenario-check-summary p {{ color:var(--muted); }}
    footer {{ width:min(1240px,calc(100% - 48px)); margin:0 auto; padding:22px 0 40px; color:var(--muted); font-size:12px; }}
    @media (max-width:900px) {{
      .top,main,footer {{ width:min(100% - 32px,760px); }}
      .split,.record,.scenario-fields {{ grid-template-columns:1fr; }}
      .scenario-field.action {{ grid-column:auto; }}
      .scenario-browser {{ grid-template-columns:1fr; min-height:0; }}
      .scenario-sidebar {{ border-right:0; border-bottom:1px solid var(--line); }}
      .scenario-nav {{ flex-direction:row; max-height:none; overflow-x:auto; overflow-y:hidden; }}
      .scenario-nav-item {{ flex:0 0 230px; min-height:92px; border-right:1px solid var(--line); border-bottom:0; }}
      .scenario-nav-item[aria-selected="true"] {{ box-shadow:inset 0 -3px 0 var(--accent); }}
    }}
    @media (max-width:560px) {{
      .top,main,footer {{ width:calc(100% - 24px); }}
      .top {{ padding:22px 0 18px; }}
      h1 {{ font-size:25px; }} h2 {{ font-size:18px; }}
      nav {{ height:auto; min-height:48px; flex-wrap:wrap; padding:10px 0; }}
      section {{ padding:20px 0; }}
      .metrics {{ grid-template-columns:1fr 1fr; }}
      .metric:nth-child(2n) {{ border-right:0; }}
      .scenario-pane-header,.scenario-tab-panel {{ padding-right:18px; padding-left:18px; }}
      .scenario-tabs {{ gap:22px; padding:0 18px; overflow-x:auto; }}
      .scenario-pane-header h3 {{ font-size:20px; }}
    }}
  </style>
</head>
<body>{body}<footer>只读派生视图 · 内容来自各 REQ 根目录当前 Markdown 定义 · source {source_digest[:12]}</footer>
<script>
(() => {{
  const scenarioTabs = [...document.querySelectorAll('[data-scenario-target]')];
  const scenarioPanes = [...document.querySelectorAll('.scenario-pane')];

  function activateDetailTab(tab, focus = false) {{
    const pane = tab.closest('.scenario-pane');
    if (!pane) return;
    const target = tab.dataset.viewTarget;
    pane.querySelectorAll('[data-view-target]').forEach(item => item.setAttribute('aria-selected', String(item === tab)));
    pane.querySelectorAll('.scenario-tab-panel').forEach(panel => {{ panel.hidden = panel.dataset.viewPanel !== target; }});
    if (focus) tab.focus();
  }}

  function activateScenario(tab, focus = false, updateHash = false) {{
    const target = tab.dataset.scenarioTarget;
    scenarioTabs.forEach(item => item.setAttribute('aria-selected', String(item === tab)));
    scenarioPanes.forEach(pane => {{ pane.hidden = pane.id !== target; }});
    if (focus) tab.focus();
    if (updateHash) history.replaceState(null, '', '#' + target.replace(/^scenario-/, ''));
  }}

  function bindArrowKeys(tabs, activate) {{
    tabs.forEach((tab, index) => tab.addEventListener('keydown', event => {{
      let next = null;
      if (event.key === 'ArrowDown' || event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next === null) return;
      event.preventDefault();
      activate(tabs[next], true, true);
    }}));
  }}

  scenarioTabs.forEach(tab => tab.addEventListener('click', () => activateScenario(tab, false, true)));
  bindArrowKeys(scenarioTabs, activateScenario);
  scenarioPanes.forEach(pane => {{
    const detailTabs = [...pane.querySelectorAll('[data-view-target]')];
    detailTabs.forEach(tab => tab.addEventListener('click', () => activateDetailTab(tab)));
    bindArrowKeys(detailTabs, activateDetailTab);
  }});

  function openHashTarget() {{
    const id = decodeURIComponent(location.hash.slice(1));
    const target = id ? document.getElementById(id) : null;
    if (!target) return false;
    const pane = target.classList.contains('scenario-pane') ? target : target.closest('.scenario-pane');
    if (!pane) return false;
    const scenarioTab = scenarioTabs.find(tab => tab.dataset.scenarioTarget === pane.id);
    if (scenarioTab) activateScenario(scenarioTab);
    if (target.classList.contains('chain-check')) {{
      const checksTab = pane.querySelector('[data-view-target="checks"]');
      if (checksTab) activateDetailTab(checksTab);
    }}
    requestAnimationFrame(() => target.scrollIntoView({{block:'start'}}));
    return true;
  }}

  if (!openHashTarget() && scenarioTabs[0]) activateScenario(scenarioTabs[0]);
  window.addEventListener('hashchange', openHashTarget);
}})();
</script></body>
</html>'''


def project_digest(project: Project) -> str:
    digest = hashlib.sha256()
    for path in sorted(project.requirement_paths.values()):
        digest.update(path.relative_to(project.root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    for mapping in (project.scenario_paths, project.matrix_paths):
        for path in sorted(mapping.values()):
            digest.update(path.relative_to(project.root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    for mapping in (project.plans, project.evidence, project.reports):
        for key in sorted(mapping):
            digest.update(str(key).encode("utf-8"))
            digest.update(repr(mapping[key]).encode("utf-8"))
    return digest.hexdigest()


def current_rows(project: Project) -> list[dict[str, Any]]:
    rows = []
    for requirement_id in sorted(project.requirements):
        requirement = as_dict(project.requirements[requirement_id].get("requirement"))
        stage, kind = delivery_stage(project, requirement_id)
        rows.append({"id": requirement_id, "requirement": requirement, "stage": stage, "kind": kind})
    return rows


def render_catalog_markdown(project: Project) -> str:
    lines = [
        "# 需求清单",
        "",
        "本文件由各 REQ 根目录当前定义自动派生，不保存独立版本或上线裁决。",
        "",
        "| REQ | 需求状态 | 交付阶段 | 标题 |",
        "|---|---|---|---|",
    ]
    for row in current_rows(project):
        requirement = row["requirement"]
        lines.append(
            f"| [{row['id']}](./{row['id']}/审核工作台.html) | {requirement.get('status')} | "
            f"{row['stage']} | {requirement.get('title')} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_catalog_html(project: Project, digest: str) -> str:
    rows = current_rows(project)
    confirmed = sum(row["requirement"].get("status") == "CONFIRMED" for row in rows)
    satisfied = sum(row["stage"] == "已验收" for row in rows)
    drafts = sum(row["requirement"].get("status") == "DRAFT" for row in rows)
    table_rows = "".join(
        f'''<tr><td class="mono"><a href="{html_escape(row['id'])}/审核工作台.html">{html_escape(row['id'])}</a></td>
        <td>{badge(row['requirement'].get('status'), 'warn' if row['requirement'].get('status') == 'DRAFT' else 'ok')}</td>
        <td>{badge(row['stage'], row['kind'])}</td>
        <td><strong>{html_escape(row['requirement'].get('title'))}</strong><div class="muted-text">{html_escape(row['requirement'].get('business_value'))}</div></td></tr>'''
        for row in rows
    )
    body = f'''<header><div class="top"><div class="eyebrow">Delivery Proof · REQ 顶层视图</div><h1>需求清单</h1><p class="sub">清单由各 REQ 的当前完整定义派生；Issue 评论时间线保存历史。</p></div></header>
    <main><nav><a href="需求清单.md">查看派生 Markdown</a></nav>
    <section><div class="metrics"><div class="metric"><strong>{len(rows)}</strong><span>REQ 总数</span></div><div class="metric"><strong>{confirmed}</strong><span>需求已确认</span></div><div class="metric"><strong>{drafts}</strong><span>需求待确认</span></div><div class="metric"><strong>{satisfied}</strong><span>已验收</span></div></div></section>
    <section><h2>独立需求</h2><table><colgroup><col style="width:260px"><col style="width:120px"><col style="width:145px"><col></colgroup><thead><tr><th>REQ</th><th>需求状态</th><th>交付阶段</th><th>标题与价值</th></tr></thead><tbody>{table_rows}</tbody></table></section></main>'''
    return html_page("需求清单", body, digest)


def list_html(values: list[Any]) -> str:
    if not values:
        return '<span class="muted-text">无</span>'
    return "<ul>" + "".join(f"<li>{html_escape(value)}</li>" for value in values) + "</ul>"


def implementation_plan_detail(plan: dict[str, Any]) -> str:
    if not plan:
        return '<p class="muted-text">尚未生成实现计划。</p>'

    context = as_dict(plan.get("context_review"))
    findings = "".join(
        f'<tr><td>{html_escape(item.get("area"))}</td><td>{html_escape(item.get("observation"))}</td><td>{html_escape(item.get("impact"))}</td></tr>'
        for item in map(as_dict, as_list(context.get("findings")))
    )
    context_findings = findings or '<tr><td colspan="3">无</td></tr>'
    context_html = (
        '<details class="implementation-detail" open><summary>上下文盘点</summary>'
        f'<p>状态：{badge(context.get("status", "未完成"), "ok" if context.get("status") == "COMPLETED" else "warn")}</p>'
        '<table><thead><tr><th>领域</th><th>已发现事实</th><th>对计划的影响</th></tr></thead>'
        f'<tbody>{context_findings}</tbody></table>'
        f'<div class="split"><div><h3>依据</h3>{list_html(as_list(context.get("project_refs")) + as_list(context.get("code_structure_refs")))}</div>'
        f'<div><h3>决策</h3>{list_html([as_dict(item).get("decision") for item in as_list(context.get("decisions"))])}</div></div>'
        '</details>'
    )

    surface_rows = []
    for surface in map(as_dict, as_list(plan.get("delivery_surfaces"))):
        entrypoints = []
        for raw_entry in as_list(surface.get("entrypoints")):
            entry = as_dict(raw_entry)
            entrypoints.append(f'{entry.get("method")} {entry.get("path")}：{entry.get("expectation")}')
        surface_rows.append(
            f'<tr><td>{html_escape(surface.get("surface"))}</td><td>{badge(surface.get("status", "未声明"), "ok" if surface.get("status") == "COMPLETED" else "info")}</td>'
            f'<td>{list_html(entrypoints)}</td><td>{list_html(as_list(surface.get("production_refs")))}</td>'
            f'<td>{list_html(as_list(surface.get("test_refs")))}</td></tr>'
        )
    surfaces = "".join(surface_rows)
    surface_fallback = surfaces or '<tr><td colspan="5">无</td></tr>'
    surfaces_html = (
        '<details class="implementation-detail" open><summary>交付面</summary>'
        '<table><thead><tr><th>面</th><th>状态</th><th>入口与预期</th><th>生产引用</th><th>测试引用</th></tr></thead>'
        f'<tbody>{surface_fallback}</tbody></table></details>'
    )

    slices = "".join(
        f'<article class="implementation-slice"><div class="slice-heading"><h3><span class="mono">{html_escape(item.get("id"))}</span> · {html_escape(item.get("title"))}</h3>{badge(item.get("status", "未声明"), "ok" if item.get("status") == "COMPLETED" else "info")}</div>'
        f'<p>{html_escape(item.get("objective"))}</p><div class="split"><div><strong>类型与依赖</strong>{list_html([item.get("kind")] + [f"依赖：{ref}" for ref in as_list(item.get("depends_on"))])}</div>'
        f'<div><strong>CHK / AST</strong>{list_html([f"CHK：{ref}" for ref in as_list(item.get("check_refs"))] + [f"AST：{ref}" for ref in as_list(item.get("assertion_refs"))])}</div></div>'
        f'<div class="split"><div><strong>生产代码</strong>{list_html(as_list(item.get("production_refs")))}</div><div><strong>测试代码</strong>{list_html(as_list(item.get("test_refs")))}</div></div></article>'
        for item in map(as_dict, as_list(plan.get("slices")))
    )
    slices_fallback = slices or '<p class="muted-text">无</p>'
    slices_html = f'<details class="implementation-detail" open><summary>实现切片详情 · {len(as_list(plan.get("slices")))} 个</summary>{slices_fallback}</details>'

    readiness = as_dict(plan.get("readiness"))
    readiness_rows = "".join(
        f'<tr><td>{html_escape(name)}</td><td>{badge(as_dict(readiness.get(name)).get("status", "未声明"), "ok" if as_dict(readiness.get(name)).get("status") == "COMPLETED" else "info")}</td><td>{html_escape(as_dict(readiness.get(name)).get("command") or as_dict(readiness.get(name)).get("readiness_probe") or ", ".join(map(str, as_list(as_dict(readiness.get(name)).get("required_refs")))))}</td></tr>'
        for name in ("configuration", "persistence", "application_start")
        if readiness.get(name) is not None
    )
    readiness_fallback = readiness_rows or '<tr><td colspan="3">无</td></tr>'
    readiness_html = f'<details class="implementation-detail" open><summary>验收前置条件</summary><table><thead><tr><th>类别</th><th>状态</th><th>要求 / 校验</th></tr></thead><tbody>{readiness_fallback}</tbody></table></details>'
    return context_html + surfaces_html + slices_html + readiness_html


def render_workbench(project: Project, requirement_id: str, digest: str) -> str:
    requirement = as_dict(project.requirements[requirement_id].get("requirement"))
    stage, stage_kind = delivery_stage(project, requirement_id)
    scenario_doc = project.scenarios.get(requirement_id)
    matrix_doc = project.matrices.get(requirement_id)
    scenarios = as_list(as_dict((scenario_doc or {}).get("acceptance_scenarios")).get("scenarios"))
    checks = as_list(as_dict((matrix_doc or {}).get("acceptance_matrix")).get("checks"))
    plan = as_dict(as_dict(project.plans.get(requirement_id, {})).get("implementation_plan"))
    human_gate = as_dict(plan.get("human_gate"))
    evidence = as_dict(as_dict(project.evidence.get(requirement_id, {})).get("test_evidence"))
    report = as_dict(as_dict(project.reports.get(requirement_id, {})).get("acceptance_report"))
    runs = as_list(evidence.get("runs"))
    artifacts = {
        str(as_dict(item).get("id")): as_dict(item)
        for item in as_list(evidence.get("artifacts"))
    }
    target_commit = report.get("git_commit") or evidence.get("git_commit")
    eligible_runs = acceptance_eligible_runs(evidence)
    eligible_run_ids = {str(item.get("id")) for item in eligible_runs}

    def run_matches_check(run: dict[str, Any], check: dict[str, Any]) -> bool:
        if str(run.get("id")) not in eligible_run_ids:
            return False
        external = as_dict(check.get("external_verification"))
        run_external = as_dict(run.get("external_verification"))
        external_matches = (
            (
                run_external.get("provider") == external.get("provider")
                and run_external.get("mode") == external.get("mode")
            )
            if external
            else run.get("external_verification") is None
        )
        required_types = as_list(as_dict(check.get("evidence_requirements")).get("required_artifact_types"))
        return external_matches and set(map(str, required_types)) <= artifact_types(as_list(run.get("artifact_refs")), artifacts)

    def run_covers_assertion(run: dict[str, Any], check: dict[str, Any], assertion_id: str) -> bool:
        assertion = next(
            (as_dict(item) for item in as_list(check.get("assertions")) if str(as_dict(item).get("id")) == assertion_id),
            {},
        )
        return (
            run_matches_check(run, check)
            and assertion_id in {str(ref) for ref in as_list(run.get("assertion_refs"))}
            and any(
                str(result.get("assertion_id")) == assertion_id
                and result.get("status") == "PASSED"
                and predicate_result_passes(assertion, result)
                for ref in as_list(run.get("artifact_refs"))
                for result in artifact_assertion_results(artifacts.get(str(ref), {}))
            )
        )

    def check_proof_status(check: dict[str, Any]) -> tuple[str, str]:
        state = check_proof_state(evidence, check, as_dict(evidence.get("definition_digests")))
        if state == "PASS":
            return "已通过", "ok"
        if state == "FAIL":
            return "未通过", "bad"
        if state == "BLOCKED":
            return "已阻塞", "warn"
        return "待验证", "muted"

    scenario_results = {
        str(as_dict(item).get("scenario_ref")): as_dict(item)
        for item in as_list(report.get("scenario_results"))
    }
    derived_scenario_results = {
        str(as_dict(item).get("id")): scenario_proof_state(
            evidence,
            checks,
            str(as_dict(item).get("id")),
            as_dict(evidence.get("definition_digests")),
        )
        for item in scenarios
    }
    checks_by_scenario: dict[str, list[dict[str, Any]]] = {}
    for value in checks:
        check = as_dict(value)
        for scenario_id in as_list(check.get("scenario_ids")):
            checks_by_scenario.setdefault(str(scenario_id), []).append(check)
    dependencies = as_list(requirement.get("dependencies"))
    checks_by_dependency: dict[str, list[dict[str, Any]]] = {}
    for value in checks:
        check = as_dict(value)
        for dependency_id in as_list(check.get("dependency_ids")):
            checks_by_dependency.setdefault(str(dependency_id), []).append(check)
    dependents = []
    for other_id in project.requirements:
        other = as_dict(project.requirements[other_id].get("requirement"))
        if any(as_dict(item).get("related_requirement_id") == requirement_id for item in as_list(other.get("dependencies"))):
            dependents.append(other_id)
    dependency_parts = []
    for value in dependencies:
        dependency = as_dict(value)
        dependency_id = str(dependency.get("id"))
        proof_checks = checks_by_dependency.get(dependency_id, [])
        blocking_checks = [check for check in proof_checks if check.get("required") is True and check.get("blocking") is True]
        blocking_statuses = [check_proof_status(check)[0] for check in blocking_checks]
        if not blocking_checks:
            dependency_status, dependency_kind = "未设计", "warn"
        elif all(status == "已通过" for status in blocking_statuses):
            dependency_status, dependency_kind = "已证明", "ok"
        elif any(status == "未通过" for status in blocking_statuses):
            dependency_status, dependency_kind = "证明失败", "bad"
        elif any(status == "已阻塞" for status in blocking_statuses):
            dependency_status, dependency_kind = "证明阻塞", "warn"
        else:
            dependency_status, dependency_kind = "待验证", "muted"
        related = dependency.get("related_requirement_id") or "无"
        proof_items = []
        for check in proof_checks:
            check_status, check_kind = check_proof_status(check)
            proof_items.append(
                f'<li><a class="mono" href="#check-{html_escape(check.get("id"))}">{html_escape(check.get("id"))}</a>'
                f'{badge("必需" if check.get("required") is True else "可选", "info" if check.get("required") is True else "muted")}'
                f'{badge("阻断" if check.get("blocking") is True else "非阻断", "info" if check.get("blocking") is True else "muted")}'
                f'{badge(check_status, check_kind)}</li>'
            )
        proof_list = '<ul class="dependency-checks">' + "".join(proof_items) + "</ul>" if proof_items else '<p class="muted-text">尚未生成证明 CHK。</p>'
        dependency_parts.append(
            f'<div class="record"><div><strong class="mono">{html_escape(dependency_id)}</strong><p>{badge(dependency_status, dependency_kind)}</p></div>'
            f'<div><p>{html_escape(dependency.get("description"))}</p><p>关联 REQ：<span class="mono">{html_escape(related)}</span>{"（仅追踪）" if dependency.get("related_requirement_id") else ""}</p><strong>证明 CHK</strong>{proof_list}</div></div>'
        )
    dependency_rows = "".join(dependency_parts) or '<p class="muted-text">当前 REQ 无业务依赖。</p>'
    def artifact_link(artifact_id: str) -> str:
        artifact = artifacts.get(artifact_id)
        if artifact is None:
            return f'<span class="mono">{html_escape(artifact_id)}</span>'
        location = str(artifact.get("location") or "")
        prefixes = (f"docs/交付证明/{requirement_id}/", f"{requirement_id}/")
        href = location
        for prefix in prefixes:
            if location.startswith(prefix):
                href = location[len(prefix):]
                break
        label = f'{artifact_id} · {artifact.get("type") or "unknown"}'
        return f'<a class="artifact-link" href="{html_escape(href)}" title="{html_escape(location)}">{html_escape(label)}</a>'

    def run_detail(run: dict[str, Any], check: dict[str, Any]) -> str:
        result = str(run.get("result"))
        if result == "BLOCKED":
            result_label, result_kind = "当前阻塞", "warn"
            qualification, qualification_kind = "尚未解除", "warn"
            reason_label = "阻塞原因"
        elif result == "FAILED":
            result_label, result_kind = "当前失败", "bad"
            qualification, qualification_kind = "尚未解除", "bad"
            reason_label = "失败原因"
        else:
            result_label, result_kind = result, "ok"
            qualification, qualification_kind = "", ""
            reason_label = "失败原因"
        artifact_refs = [str(ref) for ref in as_list(run.get("artifact_refs"))]
        artifact_links = (
            '<span class="artifact-links">' + "".join(artifact_link(ref) for ref in artifact_refs) + "</span>"
            if artifact_refs else '<span class="muted-text">无</span>'
        )
        failure_reason = run.get("failure_reason")
        supporting_refs = [str(ref) for ref in as_list(run.get("supporting_run_refs"))]
        supporting_links = (
            '<p>辅助执行：' + ", ".join(
                f'<a class="mono" href="#supporting-run-{html_escape(ref)}">{html_escape(ref)}</a>'
                for ref in supporting_refs
            ) + '</p>'
            if supporting_refs else ""
        )
        return (
            '<div class="chain-run"><div class="chain-run-head">'
            f'<strong class="mono">{html_escape(run.get("id"))}</strong>{badge(result_label, result_kind)}'
            + (badge(qualification, qualification_kind) if qualification else "")
            + f'</div><p>阶段：{html_escape(run.get("phase"))} · ART：{artifact_links}</p>'
            f'<p class="run-command">命令：{html_escape(run.get("command"))}</p>'
            + (f'<p>{reason_label}：{html_escape(failure_reason)}</p>' if failure_reason else "")
            + supporting_links
            + "</div>"
        )

    def auxiliary_run_detail(run: dict[str, Any]) -> str:
        result = str(run.get("result"))
        result_kind = "ok" if result == "PASSED" else "bad" if result == "FAILED" else "warn"
        artifact_refs = [str(ref) for ref in as_list(run.get("artifact_refs"))]
        artifact_links = (
            '<span class="artifact-links">' + "".join(artifact_link(ref) for ref in artifact_refs) + "</span>"
            if artifact_refs else '<span class="muted-text">无</span>'
        )
        failure_reason = run.get("failure_reason")
        return (
            f'<div class="chain-run" id="supporting-run-{html_escape(run.get("id"))}">'
            f'<div class="chain-run-head"><strong class="mono">{html_escape(run.get("id"))}</strong>{badge(result, result_kind)}{badge("REQ 级辅助执行", "muted")}</div>'
            f'<p>阶段：{html_escape(run.get("phase"))} · ART：{artifact_links}</p>'
            f'<p class="run-command">命令：{html_escape(run.get("command"))}</p>'
            + (f'<p>执行结果：{html_escape(failure_reason)}</p>' if failure_reason else "")
            + '</div>'
        )

    auxiliary_runs = [
        as_dict(run)
        for run in runs
        if not as_list(as_dict(run).get("check_refs")) and not as_list(as_dict(run).get("assertion_refs"))
    ]
    auxiliary_section = (
        f'<section><h2>辅助执行</h2><p class="sub">这些 RUN 属于当前 REQ 的执行准备、回归、构建或清理，不直接证明任何 CHK/AST。</p><div class="chain-runs">{"".join(auxiliary_run_detail(run) for run in auxiliary_runs)}</div></section>'
        if auxiliary_runs else ""
    )

    scenario_nav_parts = []
    scenario_detail_parts = []
    rendered_check_anchors: set[str] = set()
    for scenario_index, value in enumerate(scenarios):
        scenario = as_dict(value)
        scenario_id = str(scenario.get("id"))
        result = scenario_results.get(scenario_id)
        result_status = derived_scenario_results.get(scenario_id)
        result_status_text = {"PASS": "PASS", "BLOCKED": "已阻塞", "FAIL": "未通过"}.get(result_status, "待验证")
        result_status_class = {"PASS": "pass", "BLOCKED": "blocked", "FAIL": "fail"}.get(result_status, "pending")
        failure_types = [str(item) for item in as_list((result or {}).get("failure_types"))]
        result_badges = ""
        verdict_detail = ""
        if result is not None:
            result_badges = '<p>' + badge(result_status_text, "ok" if result_status == "PASS" else "bad") + " " + " ".join(
                badge(item, "bad")
                for item in failure_types
            ) + "</p>"
            verdict_detail = (
                f'<div class="verdict{" pass" if result_status == "PASS" else ""}"><strong>当前证明结论</strong>'
                f'<p>{html_escape(result.get("reason") or "裁决原因缺失（报告契约不完整）")}</p>'
                + "</div>"
            )
        check_parts = []
        for check in checks_by_scenario.get(scenario_id, []):
            check_id = str(check.get("id"))
            anchor = ""
            if check_id not in rendered_check_anchors:
                anchor = f' id="check-{html_escape(check_id)}"'
                rendered_check_anchors.add(check_id)
            check_runs = [as_dict(item) for item in runs if check_id in as_list(as_dict(item).get("check_refs"))]
            external = as_dict(check.get("external_verification"))
            external_text = (
                f' · 外部系统：{html_escape(external.get("provider"))} · 验证方式：{html_escape(external.get("mode"))}'
                if external else ""
            )
            assertion_coverage_parts = []
            for assertion in as_list(check.get("assertions")):
                assertion_item = as_dict(assertion)
                assertion_id = str(assertion_item.get("id"))
                proof_runs = [
                    str(run.get("id"))
                    for run in eligible_runs
                    if check_id in as_list(run.get("check_refs"))
                    and run_covers_assertion(run, check, assertion_id)
                ]
                assertion_status = "已证明" if proof_runs else "待验证"
                assertion_kind = "ok" if proof_runs else "warn"
                run_text = f'<span class="assertion-runs">RUN：{html_escape(", ".join(proof_runs) or "无")}</span>'
                outcome_text = f'<span class="assertion-runs">结果：{html_escape(", ".join(map(str, as_list(assertion_item.get("outcome_refs")))) or "未映射")}</span>'
                evidence_items = [
                    result
                    for run in eligible_runs
                    if str(run.get("id")) in proof_runs
                    for ref in as_list(run.get("artifact_refs"))
                    for result in artifact_assertion_results(artifacts.get(str(ref), {}))
                    if str(result.get("assertion_id")) == assertion_id and result.get("status") == "PASSED"
                ]
                evidence_text = ""
                if evidence_items:
                    evidence_item = evidence_items[0]
                    evidence_text = (
                        f'<span class="assertion-evidence">预期：{html_escape(evidence_item.get("expected"))}；'
                        f'实际：{html_escape(evidence_item.get("observed"))}</span>'
                    )
                assertion_coverage_parts.append(
                    f'<li><span class="mono">{html_escape(assertion_id)}</span>{badge(assertion_status, assertion_kind)}'
                    f'<span class="assertion-description">{html_escape(assertion_item.get("description"))}</span>{outcome_text}{run_text}{evidence_text}</li>'
                )
            assertion_coverage = '<strong>AST 覆盖</strong><ul class="assertion-coverage">' + "".join(assertion_coverage_parts) + "</ul>"
            dependency_ids = as_list(check.get("dependency_ids"))
            dependency_proof = (
                f' · 证明依赖：{html_escape(", ".join(map(str, dependency_ids)))}'
                if dependency_ids else ""
            )
            current_run_parts = []
            for run in check_runs:
                current_run_parts.append(run_detail(run, check))
            current_run_details = "".join(current_run_parts) or '<p class="muted-text">尚无当前 RUN 记录。</p>'
            required_artifact_types = as_list(as_dict(check.get("evidence_requirements")).get("required_artifact_types"))
            evidence_requirements_text = (
                f'<p>必需证据类型：{html_escape(", ".join(map(str, required_artifact_types)))}</p>'
                if required_artifact_types else ""
            )
            check_parts.append(
                f'<div class="chain-check"{anchor}><h4>CHK：<span class="mono">{html_escape(check_id)}</span> · {html_escape(check.get("responsibility"))}</h4>'
                f'<p>{badge(check.get("verification_type"), "info")}{external_text}{dependency_proof}</p>'
                f'{evidence_requirements_text}'
                f'{assertion_coverage}'
                f'<div class="chain-runs"><strong>当前证明</strong>{current_run_details}</div></div>'
            )
        check_chain = "".join(check_parts) or '<p class="muted-text">尚未关联 CHK。</p>'
        selected = scenario_index == 0
        if scenario.get("then"):
            then_html = '<ol class="gherkin-outcomes">' + "".join(
                f'<li><span class="mono">{html_escape(as_dict(outcome).get("id"))}</span><span>{html_escape(as_dict(outcome).get("statement"))}</span></li>'
                for outcome in as_list(scenario.get("then"))
            ) + '</ol>'
            scenario_fields = (
                f'<div class="scenario-field"><span class="scenario-field-key">GIVEN：</span><div class="scenario-field-value">{list_html(as_list(scenario.get("given")))}</div></div>'
                f'<div class="scenario-field action"><span class="scenario-field-key">WHEN：</span><div class="scenario-field-value">{html_escape(scenario.get("when"))}</div></div>'
                f'<div class="scenario-field action"><span class="scenario-field-key">THEN：</span><div class="scenario-field-value">{then_html}</div></div>'
            )
        else:
            scenario_fields = (
                f'<div class="scenario-field action"><span class="scenario-field-key">动作：</span><div class="scenario-field-value">{html_escape(scenario.get("action"))}</div></div>'
                f'<div class="scenario-field"><span class="scenario-field-key">预期结果：</span><div class="scenario-field-value">{list_html(as_list(scenario.get("expected_outcomes")))}</div></div>'
                f'<div class="scenario-field"><span class="scenario-field-key">前置条件：</span><div class="scenario-field-value">{list_html(as_list(scenario.get("preconditions")))}</div></div>'
            )
        scenario_nav_parts.append(
            f'''<button class="scenario-nav-item" id="scenario-tab-{html_escape(scenario_id)}" type="button" role="tab" aria-selected="{'true' if selected else 'false'}" aria-controls="{html_escape(scenario_id)}" data-scenario-target="{html_escape(scenario_id)}"><span class="scenario-nav-line"><span class="scenario-nav-id">{html_escape(scenario_id)}</span><span class="scenario-nav-status {result_status_class}">{html_escape(result_status_text)}</span></span><span class="scenario-nav-title">{html_escape(scenario.get('business_result'))}</span></button>'''
        )
        scenario_detail_parts.append(
            f'''<article class="scenario-pane" id="{html_escape(scenario_id)}" role="tabpanel" aria-labelledby="scenario-tab-{html_escape(scenario_id)}"{' hidden' if not selected else ''}><div class="scenario-pane-header"><div class="scenario-pane-kicker"><span class="mono">{html_escape(scenario_id)}</span>{badge(result_status_text, 'ok' if result_status == 'PASS' else 'bad' if result_status in {'BLOCKED', 'FAIL'} else 'muted')}</div><h3>{html_escape(scenario.get('business_result'))}</h3></div><div class="scenario-tabs" role="tablist" aria-label="{html_escape(scenario_id)} 详情视图"><button class="detail-tab" id="{html_escape(scenario_id)}-overview-tab" type="button" role="tab" aria-selected="true" aria-controls="{html_escape(scenario_id)}-overview" data-view-target="overview">场景说明</button><button class="detail-tab" id="{html_escape(scenario_id)}-checks-tab" type="button" role="tab" aria-selected="false" aria-controls="{html_escape(scenario_id)}-checks" data-view-target="checks">检查与证据 · {len(checks_by_scenario.get(scenario_id, []))}</button></div><div class="scenario-tab-panel" id="{html_escape(scenario_id)}-overview" role="tabpanel" aria-labelledby="{html_escape(scenario_id)}-overview-tab" data-view-panel="overview"><div class="scenario-result"><span class="scenario-result-label">业务结果</span><strong>{html_escape(scenario.get('business_result'))}</strong></div>{verdict_detail}<div class="scenario-fields">{scenario_fields}</div></div><div class="scenario-tab-panel" id="{html_escape(scenario_id)}-checks" role="tabpanel" aria-labelledby="{html_escape(scenario_id)}-checks-tab" data-view-panel="checks" hidden><div class="scenario-check-summary"><div><strong>{len(checks_by_scenario.get(scenario_id, []))} 个检查</strong><p>按 CHK → RUN 展示当前场景的验证责任和证据。</p></div>{result_badges}</div>{check_chain}</div></article>'''
        )
    scenario_browser = (
        '<div class="scenario-browser"><aside class="scenario-sidebar"><div class="scenario-nav-head"><strong>验收场景</strong>'
        f'<span class="mono">{len(scenarios)} SCN</span></div><div class="scenario-nav" role="tablist" aria-label="验收场景列表">'
        + "".join(scenario_nav_parts)
        + '</div></aside><div class="scenario-detail">'
        + "".join(scenario_detail_parts)
        + "</div></div>"
        if scenarios else '<p class="muted-text">尚未生成验收场景。</p>'
    )
    failed_results = [
        {"scenario_ref": scenario_id, "status": status}
        for scenario_id, status in derived_scenario_results.items()
        if status != "PASS"
    ]
    failed_links = ", ".join(
        f'<a class="mono" href="#{html_escape(item.get("scenario_ref"))}">{html_escape(item.get("scenario_ref"))}</a>'
        for item in failed_results
    )
    conclusion_detail = ""
    if failed_results:
        conclusion_detail = f'<p>未通过场景：{failed_links}</p>'

    report_status = (
        "SATISFIED"
        if report and derived_scenario_results and all(status == "PASS" for status in derived_scenario_results.values())
        else "NOT_SATISFIED" if report else "尚无报告"
    )
    if report_status == "NOT_SATISFIED" and not conclusion_detail:
        conclusion_detail = '<p>当前报告未通过：需要绑定一个真实 Git commit，并在该提交上重新执行全部必需阻断 CHK。</p>'
    commit_detail = f'<p>验收 Git commit：<span class="mono">{html_escape(target_commit or "未绑定")}</span></p>'
    conclusion_detail = commit_detail + conclusion_detail
    report_kind = "ok" if report_status == "SATISFIED" else "bad" if report_status == "NOT_SATISFIED" else "muted"
    gate_status = human_gate.get("status", "未声明")
    gate_kind = "ok" if gate_status == "CONFIRMED" else "warn" if gate_status == "PENDING" else "muted"
    gate_categories = ", ".join(map(str, as_list(human_gate.get("risk_categories")))) or "无"
    implementation_slices = list_html([f"{as_dict(item).get('id')} · {as_dict(item).get('title')} · {as_dict(item).get('status')}" for item in as_list(plan.get("slices"))])
    body = f'''<header><div class="top"><div class="eyebrow">REQ 审核工作台</div><h1>{html_escape(requirement.get('title'))}</h1><p>REQ：<span class="mono">{html_escape(requirement_id)}</span> · REQ 状态：{badge(requirement.get('status'), 'warn' if requirement.get('status') == 'DRAFT' else 'ok')} · 交付状态：{badge(stage, stage_kind)}</p><p class="sub">{html_escape(requirement.get('business_value'))}</p></div></header>
    <main><nav><a href="../需求清单.html">返回需求清单</a><a href="需求.md">查看需求定义文件</a></nav>
    <section><h2>当前结论</h2><div class="metrics"><div class="metric"><strong>{len(scenarios)}</strong><span>SCN</span></div><div class="metric"><strong>{len(checks)}</strong><span>CHK</span></div><div class="metric"><strong>{len(eligible_runs)}/{len(runs)}</strong><span>PASSED 正式 RUN / ��轮 RUN</span></div></div><div class="{'okline' if report_status == 'SATISFIED' else 'notice'}">验收报告：{badge(report_status, report_kind)}{conclusion_detail}</div></section>
    <section><h2>需求定义</h2><p class="statement">{html_escape(requirement.get('statement'))}</p><div class="split"><div><h3>纳入范围</h3>{list_html(as_list(as_dict(requirement.get('scope')).get('included')))}</div><div><h3>排除范围</h3>{list_html(as_list(as_dict(requirement.get('scope')).get('excluded')))}</div></div></section>
    <section><h2>业务依赖与证明</h2><div class="records">{dependency_rows}</div><p>被其他 REQ 关联：{html_escape(', '.join(dependents) or '无')}</p></section>
    <section><h2>验收链路</h2><p>验收场景：{badge(as_dict((scenario_doc or {}).get('acceptance_scenarios')).get('status', '未生成'), 'warn' if as_dict((scenario_doc or {}).get('acceptance_scenarios')).get('status') == 'DRAFT' else 'ok' if scenario_doc else 'muted')} · 验收矩阵：{badge(as_dict((matrix_doc or {}).get('acceptance_matrix')).get('status', '未生成'), 'warn' if as_dict((matrix_doc or {}).get('acceptance_matrix')).get('status') == 'DRAFT' else 'ok' if matrix_doc else 'muted')}</p><p class="sub">左侧切换验收场景；右侧在场景说明与 CHK → RUN 证明之间切换。</p>{scenario_browser}</section>
{auxiliary_section}
    <section><h2>开发实现</h2><p>实现计划：{badge(plan.get('status', '未生成'), 'info' if plan else 'muted')} · blockers：{len(as_list(plan.get('blockers')))}</p><p>人工门禁：{badge(gate_status, gate_kind)} · 风险类别：{html_escape(gate_categories)}</p>{implementation_slices}{implementation_plan_detail(plan)}</section>
    </main>'''
    return html_page(f"{requirement_id} 审核工作台", body, digest)


def expected_outputs(root: Path) -> dict[Path, str]:
    project = load_project(root.resolve())
    if project.validation.errors:
        raise ReviewError("；".join(project.validation.errors))
    digest = project_digest(project)
    outputs = {
        root / "需求清单.md": render_catalog_markdown(project),
        root / "需求清单.html": render_catalog_html(project, digest),
    }
    for requirement_id in project.requirements:
        outputs[root / requirement_id / "审核工作台.html"] = render_workbench(project, requirement_id, digest)
    return outputs


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            handle.write(content)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def run(root: Path, check: bool) -> int:
    root = root.parent if root.is_file() else root
    outputs = expected_outputs(root)
    if check:
        stale = [path for path, content in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != content]
        if stale:
            for path in stale:
                print(f"审核页不是最新派生视图: {path}", file=sys.stderr)
            return 1
        print(f"审核视图与 REQ 真值源一致: {len(outputs)} 个文件")
        return 0
    for path, content in outputs.items():
        atomic_write(path, content)
    print(f"已生成 REQ 派生清单与桌面审核页: {len(outputs)} 个文件")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_ROOT, help="docs/交付证明目录或需求清单路径")
    parser.add_argument("--check", action="store_true", help="只检查派生视图是否最新")
    args = parser.parse_args()
    try:
        return run(args.input, args.check)
    except (ReviewError, OSError, UnicodeError) as error:
        print(f"生成交付审核页失败: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
