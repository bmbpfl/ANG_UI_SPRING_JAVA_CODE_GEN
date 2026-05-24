import streamlit as st
import pandas as pd
import zipfile
import io
import os
from generators.schema_parser import SchemaParser
from generators.angular_generator import AngularGenerator
from generators.spring_generator import SpringGenerator

st.set_page_config(
    page_title="FullStack Code Generator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f4c81 100%);
    padding: 2rem 2.5rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.main-header h1 { color: #e2f0ff; font-size: 2rem; font-weight: 700; margin: 0; }
.main-header p  { color: #93c5fd; margin: 0.4rem 0 0; font-size: 0.95rem; }

.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    margin: 2px;
}
.badge-angular { background:#ff3e00; color:#fff; }
.badge-spring  { background:#6db33f; color:#fff; }
.badge-fk      { background:#f59e0b; color:#1a1a1a; }
.badge-pk      { background:#6366f1; color:#fff; }

.card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
}
.card h3 { color: #e2e8f0; margin: 0 0 0.5rem; font-size: 1rem; }
.card p  { color: #94a3b8; margin: 0; font-size: 0.85rem; }

.file-tree {
    background: #0f172a;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: #7dd3fc;
    line-height: 1.8;
}

.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0;
    padding: 8px 20px;
    font-weight: 600;
}

code, pre { font-family: 'JetBrains Mono', monospace !important; }

.success-box {
    background: #064e3b;
    border: 1px solid #10b981;
    border-radius: 8px;
    padding: 0.8rem 1.2rem;
    color: #6ee7b7;
    font-size: 0.9rem;
    margin: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>⚡ FullStack Code Generator</h1>
  <p>
    <span class="badge badge-angular">Angular 16</span>
    <span class="badge badge-spring">Spring Boot 3</span>
    &nbsp;·&nbsp; Auto-generates UI + Backend from your DB schema
  </p>
</div>
""", unsafe_allow_html=True)

# ── Load & parse schema ──────────────────────────────────────────────────────
#CSV_PATH = "/mnt/user-data/uploads/tab_struc_create_inserts_ang_ai_spring_java.csv"

uploaded_file = st.file_uploader(
    "Upload Schema CSV",
    type=["csv"]
)
if uploaded_file:
    CSV_PATH = uploaded_file 

# CSV_PATH = "tab_struc_create_inserts_ang_ai_spring_java.csv"

@st.cache_data
def load_schema(path):
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    df = df.fillna("")
    return SchemaParser(df).parse()
    
if uploaded_file:
    
    schema = load_schema(CSV_PATH)
    tables = list(schema.keys())

# ── Sidebar ──────────────────────────────────────────────────────────────────
if uploaded_file:
    with st.sidebar:
        st.markdown("### 🗂️ Schema Explorer")
        selected_table = st.selectbox("Select Table", tables, key="table_sel")
        tbl = schema[selected_table]

        st.markdown(f"**{selected_table}**")
        st.markdown(f"Fields: `{len(tbl['fields'])}`  |  FKs: `{len(tbl['foreign_keys'])}`")

        st.markdown("---")
        st.markdown("### ⚙️ Generation Options")
        gen_angular = st.checkbox("Angular 16 UI", value=True)
        gen_spring  = st.checkbox("Spring Boot Backend", value=True)
        pkg_name    = st.text_input("Java Package", value="com.fintech.app")
        api_prefix  = st.text_input("API Prefix", value="/api/v1")

        st.markdown("---")
        st.markdown("### 📋 All Tables")
        for t in tables:
            fk_count = len(schema[t]['foreign_keys'])
            badge = f' <span class="badge badge-fk">{fk_count} FK</span>' if fk_count else ""
            st.markdown(f"• **{t}**{badge}", unsafe_allow_html=True)

# ── Schema info panel ────────────────────────────────────────────────────────
if uploaded_file:
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tables", len(tables))
    with col2:
        total_fk = sum(len(schema[t]['foreign_keys']) for t in tables)
        st.metric("Foreign Keys", total_fk)
    with col3:
        st.metric("Selected Table", selected_table)
    with col4:
        st.metric("Fields in Table", len(tbl['fields']))

st.divider()

if uploaded_file:
    
# ── Table details ─────────────────────────────────────────────────────────────
    with st.expander(f"📊 Schema Details — {selected_table}", expanded=True):
        rows = []
        for f in tbl['fields']:
            fk_ref = ""
            for fk in tbl['foreign_keys']:
                if fk['column'] == f['name']:
                    fk_ref = f"→ {fk['ref_table']}.{fk['ref_column']}"
            rows.append({
                "Field": f['name'],
                "Type": f['db_type'],
                "Identity/PK": "✅" if f.get('is_identity') or f.get('is_pk') else "",
                "Required": "✅" if f.get('required') else "",
                "Max Len": f.get('max_len',''),
                "Decimals": f.get('decimals',''),
                "Indexed": "✅" if f.get('indexed') else "",
                "FK Reference": fk_ref,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── Generate ─────────────────────────────────────────────────────────────────
st.markdown("### 🚀 Generate Code")
if st.button("⚡ Generate Full Stack Code", type="primary", use_container_width=True):
    with st.spinner("Generating Angular 16 + Spring Boot code..."):
        ang_gen  = AngularGenerator(schema, pkg_name, api_prefix)
        spr_gen  = SpringGenerator(schema, pkg_name, api_prefix)

        ang_files = ang_gen.generate(selected_table) if gen_angular else {}
        spr_files = spr_gen.generate(selected_table) if gen_spring  else {}
        all_files = {**ang_files, **spr_files}

        st.session_state["generated"] = all_files
        st.session_state["table"]     = selected_table

    st.markdown('<div class="success-box">✅ Code generated successfully!</div>', unsafe_allow_html=True)

# ── Display generated code ────────────────────────────────────────────────────
if "generated" in st.session_state and st.session_state.get("table") == selected_table:
    all_files = st.session_state["generated"]

    ang_files = {k: v for k, v in all_files.items() if k.startswith("angular/")}
    spr_files = {k: v for k, v in all_files.items() if k.startswith("spring/")}

    # File tree
    st.markdown("#### 📁 Generated File Structure")
    tree_lines = [f"📦 {selected_table}-fullstack/"]
    if ang_files:
        tree_lines.append("├── 📂 angular/")
        ang_sorted = sorted(ang_files.keys())
        for i, f in enumerate(ang_sorted):
            prefix = "│   └──" if i == len(ang_sorted)-1 else "│   ├──"
            tree_lines.append(f"{prefix} 📄 {f.split('/',2)[-1]}")
    if spr_files:
        tree_lines.append("└── 📂 spring/")
        spr_sorted = sorted(spr_files.keys())
        for i, f in enumerate(spr_sorted):
            prefix = "    └──" if i == len(spr_sorted)-1 else "    ├──"
            tree_lines.append(f"{prefix} ☕ {f.split('/',2)[-1]}")

    st.markdown(f'<div class="file-tree">' + "<br>".join(tree_lines) + "</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 📝 Generated Code Files")

    tabs = []
    if ang_files: tabs.append("🅰️ Angular 16")
    if spr_files: tabs.append("☕ Spring Boot")
    tab_objs = st.tabs(tabs) if tabs else []

    idx = 0
    if ang_files:
        with tab_objs[idx]:
            idx += 1
            ang_subtabs_labels = [os.path.basename(k) for k in sorted(ang_files.keys())]
            ang_subtabs = st.tabs(ang_subtabs_labels)
            for tab, (fname, content) in zip(ang_subtabs, sorted(ang_files.items())):
                with tab:
                    ext = fname.split(".")[-1]
                    lang = {"ts": "typescript", "html": "html", "css": "css", "json": "json"}.get(ext, "text")
                    st.code(content, language=lang)

    if spr_files:
        with tab_objs[idx]:
            spr_subtabs_labels = [os.path.basename(k) for k in sorted(spr_files.keys())]
            spr_subtabs = st.tabs(spr_subtabs_labels)
            for tab, (fname, content) in zip(spr_subtabs, sorted(spr_files.items())):
                with tab:
                    st.code(content, language="java")

    # ── Download ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📥 Download")
    col_a, col_b, col_c = st.columns(3)

    def make_zip(file_dict):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, content in file_dict.items():
                zf.writestr(fname, content)
        buf.seek(0)
        return buf

    with col_a:
        if ang_files:
            st.download_button(
                "⬇️ Download Angular Code",
                data=make_zip(ang_files),
                file_name=f"{selected_table}_angular.zip",
                mime="application/zip",
                use_container_width=True
            )
    with col_b:
        if spr_files:
            st.download_button(
                "⬇️ Download Spring Boot Code",
                data=make_zip(spr_files),
                file_name=f"{selected_table}_spring.zip",
                mime="application/zip",
                use_container_width=True
            )
    with col_c:
        if all_files:
            st.download_button(
                "⬇️ Download Full Stack ZIP",
                data=make_zip(all_files),
                file_name=f"{selected_table}_fullstack.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary"
            )
