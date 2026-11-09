import html
import time
from pathlib import Path
from healcode.core.state import HealingSessionState

class ReportGenerator:
    """Generates Markdown and standalone HTML diagnostic reports of healing sessions."""

    @staticmethod
    def generate_markdown(state: HealingSessionState, output_path: Path) -> Path:
        output_path = Path(output_path)
        status_badge = "✅ HEALED" if state.is_healed else "❌ UNRESOLVED"
        
        lines = [
            f"# HealCode Diagnostic & Self-Healing Report",
            f"",
            f"- **Status**: {status_badge}",
            f"- **Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(state.start_time))}",
            f"- **Total Duration**: {state.total_duration_seconds:.2f} seconds",
            f"- **Healing Iterations**: {state.current_iteration}/{state.max_iterations}",
            f"- **Initial Test Failures**: {len(state.initial_failures)}",
            f"- **Modified Files**: {', '.join(state.modified_files) if state.modified_files else 'None'}",
            f"",
            f"---",
            f"",
            f"## 📋 Initial Test Failures",
            f"",
        ]

        for failure in state.initial_failures:
            lines.extend([
                f"### `{failure.name}`",
                f"- **Status**: `{failure.status}`",
                f"- **Location**: `{failure.file_path or 'unknown'}:{failure.line_number or ''}`",
                f"- **Error Message**: `{failure.message}`",
                f"",
                f"```text",
                failure.traceback or failure.message or "No traceback",
                f"```",
                f"",
            ])

        lines.extend([
            f"---",
            f"",
            f"## 🔄 Healing Iterations",
            f"",
        ])

        for it in state.iterations:
            result_str = "PASSED" if it.success else "FAILED"
            lines.extend([
                f"### Iteration {it.iteration_number}: {result_str}",
                f"",
            ])
            if it.proposal:
                lines.extend([
                    f"**Root Cause Analysis:**",
                    f"> {it.proposal.root_cause_analysis}",
                    f"",
                    f"**Fix Hypothesis:**",
                    f"> {it.proposal.fix_hypothesis}",
                    f"",
                    f"- **Confidence**: {int(it.proposal.confidence_score * 100)}%",
                    f"- **Risk Assessment**: {it.proposal.risk_assessment}",
                    f"",
                ])
            if it.diff:
                lines.extend([
                    f"#### Applied Patch (Diff):",
                    f"```diff",
                    it.diff,
                    f"```",
                    f"",
                ])

        lines.extend([
            f"---",
            f"",
            f"*(Generated automatically by HealCode & Google Gemini)*",
        ])

        content = "\n".join(lines)
        output_path.write_text(content, encoding="utf-8")
        return output_path

    @staticmethod
    def generate_html(state: HealingSessionState, output_path: Path) -> Path:
        output_path = Path(output_path)
        status_color = "#10b981" if state.is_healed else "#ef4444"
        status_text = "HEALED" if state.is_healed else "UNRESOLVED"
        
        diff_html = ""
        if state.last_diff:
            diff_html = f"<pre class='diff-block'><code>{html.escape(state.last_diff)}</code></pre>"
        else:
            diff_html = "<p class='text-muted'>No diff recorded.</p>"

        iterations_html = ""
        for it in state.iterations:
            badge_color = "#10b981" if it.success else "#f59e0b"
            prop_html = ""
            if it.proposal:
                prop_html = f"""
                <div class="card my-2">
                    <p><strong>Root Cause:</strong> {html.escape(it.proposal.root_cause_analysis)}</p>
                    <p><strong>Fix Hypothesis:</strong> {html.escape(it.proposal.fix_hypothesis)}</p>
                    <p><strong>Confidence:</strong> {int(it.proposal.confidence_score * 100)}% | <strong>Risk:</strong> {html.escape(it.proposal.risk_assessment)}</p>
                </div>
                """
            it_diff = ""
            if it.diff:
                it_diff = f"<pre class='diff-block'><code>{html.escape(it.diff)}</code></pre>"

            iterations_html += f"""
            <div class="iteration-card">
                <h4>Iteration {it.iteration_number} <span class="badge" style="background: {badge_color};">{'SUCCESS' if it.success else 'FAILED'}</span></h4>
                {prop_html}
                {it_diff}
            </div>
            """

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HealCode Diagnostic Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            margin: 0;
            padding: 2rem;
            line-height: 1.5;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}
        .badge {{
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-weight: bold;
            font-size: 0.875rem;
            color: #fff;
        }}
        .card {{
            background: #1e293b;
            border-radius: 8px;
            padding: 1.25rem;
            margin-bottom: 1.5rem;
            border: 1px solid #334155;
        }}
        .diff-block {{
            background: #090d16;
            border-radius: 6px;
            padding: 1rem;
            overflow-x: auto;
            color: #38bdf8;
            font-family: "Courier New", Courier, monospace;
            border: 1px solid #1e293b;
        }}
        .text-muted {{ color: #94a3b8; }}
        h1, h2, h3, h4 {{ color: #f8fafc; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>⚡ HealCode Diagnostic Report</h1>
                <p class="text-muted">Generated by Google Gemini & HealCode Agent</p>
            </div>
            <div>
                <span class="badge" style="background: {status_color}; font-size: 1.1rem; padding: 0.5rem 1rem;">{status_text}</span>
            </div>
        </div>

        <div class="card">
            <h3>Session Summary</h3>
            <p><strong>Duration:</strong> {state.total_duration_seconds:.2f} seconds</p>
            <p><strong>Iterations:</strong> {state.current_iteration} of {state.max_iterations}</p>
            <p><strong>Modified Files:</strong> {html.escape(', '.join(state.modified_files) if state.modified_files else 'None')}</p>
        </div>

        <h2>Healing History</h2>
        {iterations_html}
    </div>
</body>
</html>
"""
        output_path.write_text(html_content, encoding="utf-8")
        return output_path
