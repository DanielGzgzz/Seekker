import streamlit as st
import pandas as pd
import plotly.express as px
import time
import random
import json
import os

# Set page config
st.set_page_config(page_title="Synthetic Market Analysis", layout="wide")

# Load wildcards
@st.cache_data
def load_wildcards():
    try:
        with open("wildcards/israeli_population_10k.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

WILDCARDS = load_wildcards()

# Try to initialize Vertex AI
def init_vertex():
    PROJECT_ID = os.environ.get("PROJECT_ID", "your-gcp-project")
    REGION = os.environ.get("REGION", "us-central1")
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        vertexai.init(project=PROJECT_ID, location=REGION)
        return GenerativeModel("gemini-1.5-pro-preview-0409"), False
    except Exception as e:
        return None, True

gen_model, FORCE_MOCK = init_vertex()

def analyze_mock() -> dict:
    time.sleep(2) # Simulate network delay
    return {
        "overall_market_fit_score": 7.5,
        "executive_summary": "[MOCK] The product shows strong potential among secular tech workers but faces skepticism from traditional households regarding price.",
        "demographic_breakdown": [
            {
                "group_name": "Secular Tech Workers",
                "affinity_score": 8.5,
                "key_objections": ["Battery life concerns", "Lack of fast charging stations"],
                "selling_points": ["Environmental impact", "Cutting-edge tech"],
                "representative_quote": "[MOCK] 'I love the idea, but I need to know it won't die on my commute to Tel Aviv.'"
            },
            {
                "group_name": "Traditional Families",
                "affinity_score": 5.0,
                "key_objections": ["Too expensive upfront", "Not enough trunk space for kids"],
                "selling_points": ["Lower long-term maintenance costs"],
                "representative_quote": "[MOCK] 'It's nice, but I can't justify the price tag right now with three kids.'"
            }
        ]
    }

def analyze_real(pitch: str, target: str, profiles: list) -> dict:
    prompt = f"""
    You are an expert product-market fit analyst. I am launching a new product/service.

    Product Pitch:
    "{pitch}"

    Target Demographic Idea:
    "{target}"

    Here is a representative panel of {len(profiles)} synthetic Israeli demographic profiles that fit this target:
    {json.dumps(profiles, indent=2)}

    Please simulate a focus group with this panel. Analyze how well this product fits them,
    what their primary objections would be, and score their affinity.

    You MUST return ONLY a valid JSON object matching this schema exactly:
    {{
      "overall_market_fit_score": 0.0 to 10.0,
      "executive_summary": "1 paragraph summary of the panel's reaction",
      "demographic_breakdown": [
        {{
           "group_name": "e.g. Secular Tech Workers",
           "affinity_score": 0.0 to 10.0,
           "key_objections": ["list", "of", "objections"],
           "selling_points": ["list", "of", "selling", "points"],
           "representative_quote": "A single sentence quote simulating a persona from this group."
        }}
      ]
    }}

    Do not wrap the JSON in markdown blocks (e.g. ```json). Just return the raw JSON string.
    """
    try:
        response = gen_model.generate_content(prompt)
        text_resp = response.text.strip()
        if text_resp.startswith("```json"): text_resp = text_resp[7:-3].strip()
        elif text_resp.startswith("```"): text_resp = text_resp[3:-3].strip()
        return json.loads(text_resp)
    except Exception as e:
        st.error(f"Vertex AI Error: {e}")
        return None

# --- UI Layout ---

st.title("📊 Synthetic Market Analysis Dashboard")
st.markdown("Instantly test product ideas against a statistically accurate, AI-generated synthetic Israeli population.")

# Sidebar Inputs
with st.sidebar:
    st.header("1. Configure Audience")
    panel_size = st.slider("Panel Size (Profiles)", min_value=10, max_value=500, value=50, step=10)

    st.header("2. Configure Product")
    product_pitch = st.text_area("Product Pitch", "An AI-powered robot that folds laundry.")
    target_demo = st.text_input("Target Audience Idea", "Busy professionals")

    st.header("3. Simulation Settings")
    mock_mode = st.checkbox("Enable Mock Mode (Skip real AI calls)", value=FORCE_MOCK)

    if FORCE_MOCK:
        st.warning("⚠️ Running in Mock Mode because GCP credentials were not found. See CREDENTIALS_GUIDE.txt to set up real AI access.")

    run_btn = st.button("Run Simulation 🚀", type="primary", use_container_width=True)

if run_btn:
    if not WILDCARDS:
        st.error("Wildcards file not found! Please run `python wildcards/generate_wildcards.py` first.")
        st.stop()

    with st.spinner(f"Sampling a highly detailed synthetic panel of {panel_size} profiles from the 10,000 wildcard pool..."):
        profiles = random.sample(WILDCARDS, panel_size)
        df = pd.DataFrame(profiles)

    st.success(f"Sampled {panel_size} synthetic profiles.")

    # --- Dashboard Tabs ---
    tab1, tab2, tab3 = st.tabs(["Market Analysis", "Population Demographics", "Financial & Social Stats"])

    # Run the AI Analysis
    with st.spinner("Interviewing the synthetic panel via Vertex AI Gemini..."):
        if mock_mode:
            report = analyze_mock()
        else:
            report = analyze_real(product_pitch, target_demo, profiles)

    if not report:
        st.stop()

    # --- TAB 1: Market Analysis ---
    with tab1:
        st.header("Overall Market Fit")
        score = report.get('overall_market_fit_score', 0)

        # Display large metric
        st.metric(label="Fit Score (Out of 10)", value=score)
        st.progress(score / 10.0)

        st.subheader("Executive Summary")
        st.info(report.get('executive_summary', ''))

        st.header("Sentiment by Group")
        breakdown = report.get('demographic_breakdown', [])

        if breakdown:
            # Bar chart for affinity
            b_df = pd.DataFrame(breakdown)
            fig_bar = px.bar(b_df, x='group_name', y='affinity_score',
                             title="Affinity Score by Demographic Cluster",
                             color='affinity_score', color_continuous_scale="Blues")
            st.plotly_chart(fig_bar, use_container_width=True)

            # Detailed breakdown
            for group in breakdown:
                with st.expander(f"{group.get('group_name')} - Score: {group.get('affinity_score')}"):
                    st.write(f"🗣️ **Quote:** *\"{group.get('representative_quote')}\"*")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("🟢 **Selling Points**")
                        for sp in group.get('selling_points', []):
                            st.write(f"- {sp}")
                    with col2:
                        st.write("🔴 **Key Objections**")
                        for obj in group.get('key_objections', []):
                            st.write(f"- {obj}")

    # --- TAB 2: Population Demographics ---
    with tab2:
        st.header("Cohort Profile: Who are we testing?")
        col1, col2 = st.columns(2)

        with col1:
            fig_rel = px.pie(df, names='Religiosity', title="Religiosity Breakdown", hole=0.4)
            st.plotly_chart(fig_rel, use_container_width=True)

        with col2:
            fig_eth = px.pie(df, names='Ethnicity', title="Ethnicity Breakdown", hole=0.4)
            st.plotly_chart(fig_eth, use_container_width=True)

        st.subheader("Age Distribution")
        fig_age = px.histogram(df, x="Age", nbins=20, title="Age Distribution of the Panel")
        st.plotly_chart(fig_age, use_container_width=True)

    # --- TAB 3: Financial & Social Stats ---
    with tab3:
        st.header("Financial & Social Insights")
        col1, col2 = st.columns(2)

        with col1:
            fig_inc = px.pie(df, names='Income', title="Income Brackets", hole=0.4)
            st.plotly_chart(fig_inc, use_container_width=True)

        with col2:
            fig_pol = px.pie(df, names='Political_Views', title="Political Orientation", hole=0.4)
            st.plotly_chart(fig_pol, use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            st.subheader("Assets vs Liabilities")
            # Count combinations
            fig_assets = px.histogram(df, x="Assets", color="Income", title="Assets by Income Level")
            st.plotly_chart(fig_assets, use_container_width=True)
        with col4:
            fig_liab = px.histogram(df, x="Liabilities", color="Age", title="Liabilities by Age")
            st.plotly_chart(fig_liab, use_container_width=True)

        st.subheader("Top Hobbies")
        # Flatten hobbies list
        all_hobbies = [h for sublist in df['Hobbies'] for h in sublist]
        hobby_counts = pd.Series(all_hobbies).value_counts().reset_index()
        hobby_counts.columns = ['Hobby', 'Count']
        fig_hob = px.bar(hobby_counts, x='Hobby', y='Count', title="Most Popular Hobbies in the Cohort")
        st.plotly_chart(fig_hob, use_container_width=True)

        st.subheader("Raw Data Sample")
        st.dataframe(df.head(10))
