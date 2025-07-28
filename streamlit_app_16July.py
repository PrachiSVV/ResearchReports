import os
import streamlit as st
import pymongo
from pymongo import MongoClient
from datetime import datetime
import pandas as pd
from html import escape


# Setup MongoDB
mongo_client = MongoClient(st.secrets['mongodb']['uri'])
collection = mongo_client["CAG_CHATBOT"]["ResearchReportTest4dot1"]

st.set_page_config(page_title="Research Report Explorer", layout="wide")
st.title("📊 Equity Research Report Explorer")

# Preferred sectoral report field order
FIELD_ORDER = [
    "sector", "period_covered", "analysts", "executive_summary",
    "overall_sentiment", "overall_sentiment_triggers", "sector_highlights",
    "industry_metrics_tables", "charts_and_figures", "macro_trends",
    "headwinds_tailwinds", "key_statistics", "top_companies", "weak_companies",
    "company_wise_detail", "conclusion", "data_sources", "sector_specific"
]
def local_file_url(pdf_id):
    html_path = os.path.abspath(
        os.path.join(
            r"static/html_files", f"{pdf_id}_report.html"
        )
    )
    # Convert Windows path to file URL
    return "file:///" + html_path.replace("\\", "/")


def render_list(lst):
    if not lst: return ""
    return "<ul>" + "".join(f"<li>{escape(str(item))}</li>" for item in lst) + "</ul>"

def render_table(table_data, description=""):
    # Assume CSV for simplicity
    import pandas as pd
    from io import StringIO
    try:
        df = pd.read_csv(StringIO(table_data))
        html_table = df.to_html(index=False, border=1)
        return f"<div><p>{escape(description)}</p>{html_table}</div>"
    except Exception:
        # Fallback: show as pre
        return f"<div><p>{escape(description)}</p><pre>{escape(table_data)}</pre></div>"


def render_sectoral_report(data, field_order):
    html = ["""
    <html>
    <head>
    <meta charset="UTF-8">
    <title>Sectoral Report</title>
    <style>
    body,div,ul,li,p,h1,h2,h3,h4 { font-family: 'Segoe UI', 'Roboto', sans-serif; }
    .report-box { background: #f7fafd; border-radius: 16px; border: 1px solid #cde3f7; padding: 32px 24px; margin-bottom:24px; }
    h1 { color: #2261a8; }
    h2, h3 { color: #2674c2; margin-top: 1.6em;}
    h4 { color: #195280; margin-bottom: 0.5em;}
    ul { padding-left: 1.2em; }
    li { margin-bottom: 0.5em;}
    table { border-collapse: collapse; margin: 12px 0;}
    table, th, td { border: 1px solid #9ec6e7; }
    th, td { padding: 8px 12px; }
    .section { margin-bottom: 2em; }
    </style>
    </head>
    <body>
    <div class="report-box">
    """]
    for field in field_order:
        value = data.get(field)
        if not value:
            continue
        html.append(f"<h3>{field.replace('_',' ').title()}</h3>")
        if isinstance(value, list):
            if field == "industry_metrics_tables":
                for tbl in value:
                    html.append(f"<h4>{escape(tbl['title'])}</h4>")
                    html.append(render_table(tbl["table_data"], tbl.get("description","")))
            elif field == "charts_and_figures":
                html.append(render_list([f"<b>{c['title']}</b>: {c['description']}" for c in value]))
            elif field in ["top_companies", "weak_companies"]:
                html.append("<ul>")
                for item in value:
                    html.append(
                        f"<li><b>{escape(item['name'])}</b>: {escape(item['performance_summary'])}"
                        + (f"<br><em>Rationale:</em> {escape(item.get('rationale',''))}" if 'rationale' in item else "")
                        + "</li>")
                html.append("</ul>")
            elif field == "company_wise_detail":
                for comp in value:
                    html.append(f"<h4>{escape(comp['name'])} <span style='color:gray'>({escape(comp['sentiment'])})</span></h4>")
                    html.append(f"<b>Summary:</b> {escape(comp.get('brief_summary',''))}<br>")
                    if comp.get("sentiment_triggers"):
                        html.append(f"<b>Triggers:</b> {render_list(comp['sentiment_triggers'])}")
                    if comp.get("metrics"):
                        html.append(f"<b>Metrics:</b><br><pre>{escape(comp['metrics'])}</pre>")
                    html.append(f"<b>Outlook/Guidance:</b> {escape(comp.get('outlook_guidance',''))}<br>")
            elif field == "analysts":
                html.append(render_list(value))
            else:
                html.append(render_list(value))
        elif isinstance(value, dict):
            html.append("<ul>")
            for k, v in value.items():
                if isinstance(v, list):
                    html.append(f"<li><b>{escape(k)}:</b> {render_list(v)}</li>")
                else:
                    html.append(f"<li><b>{escape(k)}:</b> {escape(str(v))}</li>")
            html.append("</ul>")
        else:
            html.append(f"<p>{escape(str(value))}</p>")
    html.append('</div></body></html>')
    return "\n".join(html)



# Fetch all processed reports
docs = list(collection.find({"status": "analysed"}))
if not docs:
    st.warning("No processed reports available.")
    st.stop()

# DataFrame for sidebar/table
df = pd.DataFrame([{
    "PDF ID": doc["_id"],
    "Title": doc.get("title", ""),
    "Company Names": ", ".join(doc.get("company_names", [])),
    "Category": doc.get("category"),
    "Auto Category": doc.get("auto_category"),
    "Published Date": doc.get("published_date"),
    "Source": doc.get("metadata", {}).get("source"),
    "Preview": doc.get("metadata", {}).get("text_preview", ""),
    "File Name": doc.get("file_name", doc.get("metadata", {}).get("file_name")),
} for doc in docs])

# Sidebar filters
with st.sidebar:
    st.header("🔍 Filters")
    companies = st.multiselect(
        "Company",
        sorted(set(sum([doc.get("company_names", []) for doc in docs], [])))
    )
    categories = st.multiselect("Category", sorted(df["Category"].dropna().unique()))
    sources = st.multiselect("Source", sorted(df["Source"].dropna().unique()))
    date_range = st.date_input("Date Range", [])

# Apply filters
filtered_df = df.copy()
if companies:
    filtered_df = filtered_df[filtered_df["Company Names"].apply(lambda x: any(c in x for c in companies))]
if categories:
    filtered_df = filtered_df[filtered_df["Category"].isin(categories)]
if sources:
    filtered_df = filtered_df[filtered_df["Source"].isin(sources)]
if len(date_range) == 2:
    start, end = map(lambda d: d.strftime("%Y-%m-%d"), date_range)
    filtered_df = filtered_df[
        filtered_df["Published Date"].between(start, end)
    ]
def http_file_url(pdf_id):
    # Returns the URL where your local HTTP server serves the HTML file
    return f"/~/static/html_files/{pdf_id}_report.html"
# Display filtered results
st.markdown(f"**Results: {len(filtered_df)} reports**")


for _, row in filtered_df.iterrows():
    doc = next((d for d in docs if d["_id"] == row["PDF ID"]), None)
    
    if not doc:
        continue
    with st.expander(f"📄 {row['Title']} — ({row['Category']})"):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**PDF ID:** {row['PDF ID']}")
            st.markdown(f"**Published Date:** {row['Published Date']}")
            st.markdown(f"**Source:** {row['Source']}")
            st.markdown(f"**Category:** {row['Category']}")
            # st.markdown(f"**Preview:**\n{row['Preview'][:500]}...")

            file_path = os.path.join(
                r"static/html_files", f"{row['PDF ID']}_report.html"
            )
            if os.path.exists(file_path):
                # Open in new tab (served by local HTTP server)
                file_url = http_file_url(row["PDF ID"])
                st.markdown(
                    f'<a href="{file_url}" target="_blank">🌐 Open HTML Report in New Tab</a>',
                    unsafe_allow_html=True
                )
                # Download button
                with open(file_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Download HTML Report",
                        data=f,
                        file_name=f"{row['PDF ID']}_report.html",
                        mime="text/html",
                        key=row["PDF ID"]+"_download_html"
                    )
            else:
                st.info("HTML report file not found.")

        with col2:
            pass
# for _, row in filtered_df.iterrows():
#     doc = next((d for d in docs if d["_id"] == row["PDF ID"]), None)
#     if not doc:
#         continue
#     with st.expander(f"📄 {row['PDF ID']} — ({row['Category']})"):
#         col1, col2 = st.columns([3, 1])
#         with col1:
#             st.markdown(f"**Published Date:** {row['Published Date']}")
#             st.markdown(f"**Source:** {row['Source']}")
#             st.markdown(f"**Category:** {row['Category']}")
#             st.markdown(f"**Preview:**\n{row['Preview'][:500]}...")

#             file_path = os.path.join(
#                 r"html_files", f"{row['PDF ID']}_report.html"
#             )
#             if os.path.exists(file_path):
#                 file_url = local_file_url(row["PDF ID"])
#                 print(file_url)
#                 st.markdown(
#                     f'<a href="{file_url}" target="_blank">🌐 Open HTML Report in New Tab</a>',
#                     unsafe_allow_html=True
#                 )
#             else:
#                 st.info("HTML report file not found.")


#         with col2:
#             pass
#             # file_path = f"downloads/{row['File Name']}"
#             # if os.path.exists(file_path):
#             #     with open(file_path, "rb") as f:
#             #         st.download_button(
#             #             label="⬇ Download PDF",
#             #             data=f,
#             #             file_name=row["File Name"],
#             #             mime="application/pdf",
#             #             key=row["PDF ID"]+"_download"
#             #         )
