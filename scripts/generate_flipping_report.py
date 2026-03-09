#!/usr/bin/env python3
"""
Generate HTML report from flipping feedback analysis.

Usage:
    python scripts/generate_flipping_report.py [--output path]
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from html import escape

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.database import (
    check_connection,
    get_topics_for_report,
    get_topic_evidence,
    get_flipping_report_stats,
    get_top_vocal_users,
)


def _intensity_badge(intensity: str) -> str:
    colors = {'high': '#e74c3c', 'medium': '#f39c12', 'low': '#95a5a6'}
    color = colors.get(intensity, '#95a5a6')
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:10px;font-size:0.8rem;">{escape(intensity)}</span>'


def _type_badge(feedback_type: str) -> str:
    colors = {
        'pain': '#e74c3c',
        'feature_request': '#3498db',
        'dislike': '#e67e22',
        'like': '#27ae60',
    }
    labels = {
        'pain': 'Pain',
        'feature_request': 'Feature Request',
        'dislike': 'Dislike',
        'like': 'Like',
    }
    color = colors.get(feedback_type, '#95a5a6')
    label = labels.get(feedback_type, feedback_type)
    return f'<span style="background:{color};color:white;padding:2px 10px;border-radius:10px;font-size:0.8rem;">{label}</span>'


def _render_topic_section(title: str, section_id: str, topics: list, icon: str, accent_color: str) -> str:
    if not topics:
        return ""

    html = f"""
        <section id="{section_id}">
            <h2><span>{icon}</span> {escape(title)}</h2>
            <div style="padding: 20px;">
    """

    for topic in topics:
        tools = topic.get('tools_mentioned') or []
        tools_html = ""
        if tools:
            tools_html = " ".join(
                f'<span style="background:#ecf0f1;padding:2px 8px;border-radius:5px;font-size:0.85rem;margin-right:4px;">{escape(t)}</span>'
                for t in tools if t
            )

        evidence = get_topic_evidence(topic['id'], limit=5)
        quotes_html = ""
        for ev in evidence:
            author = escape(ev.get('author') or 'anonymous')
            quote = escape(ev.get('original_quote') or ev.get('description', ''))
            intensity = ev.get('sentiment_intensity', 'medium')
            quotes_html += f"""
                <div style="border-left:3px solid {accent_color};padding:8px 12px;margin:8px 0;background:#f8f9fa;">
                    <div style="font-style:italic;color:#555;">"{quote}"</div>
                    <div style="font-size:0.85rem;color:#888;margin-top:4px;">
                        — u/{author} {_intensity_badge(intensity)}
                    </div>
                </div>
            """

        html += f"""
            <div style="border:1px solid #e0e0e0;border-radius:8px;padding:20px;margin-bottom:20px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
                    <h3 style="margin:0;color:#2c3e50;">{escape(topic['topic_title'])}</h3>
                    <div style="text-align:right;white-space:nowrap;margin-left:20px;">
                        <div style="font-size:1.5rem;font-weight:bold;color:{accent_color};">{topic['unique_user_count']}</div>
                        <div style="font-size:0.8rem;color:#888;">unique users</div>
                    </div>
                </div>
                <div style="color:#555;margin-bottom:10px;">{escape(topic['topic_summary'])}</div>
                <div style="margin-bottom:10px;">
                    <strong style="font-size:0.85rem;color:#888;">MENTIONS:</strong> {topic['total_item_count']}
                    &nbsp;&nbsp;
                    <strong style="font-size:0.85rem;color:#888;">TOOLS:</strong> {tools_html or '<span style="color:#aaa;">General</span>'}
                </div>
                <div>
                    <strong style="font-size:0.85rem;color:#888;">TOP QUOTES:</strong>
                    {quotes_html}
                </div>
            </div>
        """

    html += """
            </div>
        </section>
    """
    return html


def generate_report(output_path: str) -> None:
    """Generate the full HTML report."""
    stats = get_flipping_report_stats()

    # Fetch topics by type
    pain_topics = get_topics_for_report('pain', limit=20)
    request_topics = get_topics_for_report('feature_request', limit=20)
    dislike_topics = get_topics_for_report('dislike', limit=20)
    like_topics = get_topics_for_report('like', limit=20)

    # Vocal users
    vocal_users = get_top_vocal_users(limit=20)

    items_by_type = stats.get('items_by_type', {})

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flipping Feedback Analysis Report</title>
    <style>
        :root {{
            --primary: #2c3e50;
            --secondary: #3498db;
            --accent: #e74c3c;
            --success: #27ae60;
            --warning: #f39c12;
            --light: #ecf0f1;
            --dark: #1a252f;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6; color: #333; background: #f5f6fa;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        header {{
            background: linear-gradient(135deg, var(--primary), var(--dark));
            color: white; padding: 40px 20px; text-align: center;
            margin-bottom: 30px; border-radius: 10px;
        }}
        header h1 {{ font-size: 2.5rem; margin-bottom: 10px; }}
        header p {{ font-size: 1.1rem; opacity: 0.9; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px; margin-bottom: 40px;
        }}
        .stat-card {{
            background: white; padding: 25px; border-radius: 10px;
            text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .stat-card .number {{
            font-size: 2.5rem; font-weight: bold; color: var(--secondary);
        }}
        .stat-card .label {{
            color: #666; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;
        }}
        section {{
            background: white; margin-bottom: 30px; border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden;
        }}
        section h2 {{
            background: var(--primary); color: white; padding: 20px 25px;
            font-size: 1.4rem; display: flex; align-items: center; gap: 10px;
        }}
        table {{
            width: 100%; border-collapse: collapse;
        }}
        th, td {{
            padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee;
        }}
        th {{ background: #f8f9fa; font-weight: 600; color: #555; }}
        tr:hover {{ background: #f8f9fa; }}
        nav {{
            background: white; padding: 15px 25px; border-radius: 10px;
            margin-bottom: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        nav a {{
            color: var(--secondary); text-decoration: none; margin-right: 20px;
            font-weight: 500;
        }}
        nav a:hover {{ text-decoration: underline; }}
        footer {{
            text-align: center; padding: 30px; color: #888; font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Flipping Feedback Analysis</h1>
            <p>What resellers love, hate, and wish for in their tools &amp; workflow</p>
            <p style="opacity:0.7;font-size:0.9rem;">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </header>

        <nav>
            <a href="#executive-summary">Summary</a>
            <a href="#pains">Top Pains</a>
            <a href="#requests">Feature Requests</a>
            <a href="#dislikes">Dislikes</a>
            <a href="#likes">Likes</a>
            <a href="#vocal-users">User Voice Index</a>
        </nav>

        <section id="executive-summary">
            <h2><span>&#128202;</span> Executive Summary</h2>
            <div style="padding: 20px;">
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="number">{stats['posts_analyzed']:,}</div>
                        <div class="label">Posts Analyzed</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{stats['total_items']:,}</div>
                        <div class="label">Feedback Items</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{stats['unique_users']:,}</div>
                        <div class="label">Unique Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="number">{stats['total_topics']:,}</div>
                        <div class="label">Topics Identified</div>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;">
                    <div style="text-align:center;padding:10px;">
                        {_type_badge('pain')} <strong>{items_by_type.get('pain', 0):,}</strong>
                    </div>
                    <div style="text-align:center;padding:10px;">
                        {_type_badge('feature_request')} <strong>{items_by_type.get('feature_request', 0):,}</strong>
                    </div>
                    <div style="text-align:center;padding:10px;">
                        {_type_badge('dislike')} <strong>{items_by_type.get('dislike', 0):,}</strong>
                    </div>
                    <div style="text-align:center;padding:10px;">
                        {_type_badge('like')} <strong>{items_by_type.get('like', 0):,}</strong>
                    </div>
                </div>
            </div>
        </section>

        {_render_topic_section("Top Pains", "pains", pain_topics, "&#128293;", "#e74c3c")}
        {_render_topic_section("Feature Requests", "requests", request_topics, "&#128161;", "#3498db")}
        {_render_topic_section("Top Dislikes", "dislikes", dislike_topics, "&#128078;", "#e67e22")}
        {_render_topic_section("What's Working (Don't Break These)", "likes", like_topics, "&#128077;", "#27ae60")}

        <section id="vocal-users">
            <h2><span>&#128483;</span> User Voice Index — Top 20 Most Vocal Users</h2>
            <div style="padding: 20px;">
                <p style="color:#666;margin-bottom:15px;">These users provide the most feedback — potential beta testers or advisory board candidates.</p>
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>User</th>
                            <th>Feedback Items</th>
                            <th>Feedback Types</th>
                            <th>Tools Mentioned</th>
                        </tr>
                    </thead>
                    <tbody>
"""

    for i, user in enumerate(vocal_users, 1):
        author = escape(user.get('author') or '?')
        types_list = user.get('types') or []
        types_html = " ".join(_type_badge(t) for t in types_list)
        tools_list = user.get('tools') or []
        tools_html = ", ".join(escape(t) for t in tools_list[:5]) if tools_list else '<span style="color:#aaa;">—</span>'

        html += f"""
                        <tr>
                            <td>{i}</td>
                            <td><strong>u/{author}</strong></td>
                            <td>{user['item_count']}</td>
                            <td>{types_html}</td>
                            <td>{tools_html}</td>
                        </tr>
        """

    html += """
                    </tbody>
                </table>
            </div>
        </section>

        <footer>
            <p>Generated from analysis of flipping/reselling Reddit posts | LLM-powered feedback extraction &amp; topic clustering</p>
        </footer>
    </div>
</body>
</html>
"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Report written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate flipping feedback HTML report')
    parser.add_argument('--output', type=str,
                        default='reports/flipping_feedback_report.html',
                        help='Output HTML file path')
    args = parser.parse_args()

    print("=" * 70)
    print("FLIPPING FEEDBACK REPORT GENERATOR")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    print("\nChecking database connection...")
    if not check_connection():
        print("ERROR: Cannot connect to database.")
        sys.exit(1)
    print("Database connection OK")

    generate_report(args.output)

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
