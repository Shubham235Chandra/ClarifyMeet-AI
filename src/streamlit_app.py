import os
import json
import streamlit as st
from google import genai

# CONFIG_PATH = "src/streamlit_app.py"
TAB_NAMES = ["Summary", "Actions", "Decisions", "Risks"]


# def load_api_key() -> str:
#     """Load Gemini API key from Streamlit secrets, env var, or config.json."""
#     # 1) Try Streamlit secrets (catch if secrets.toml doesn't exist)
#     try:
#         api_key = st.secrets["GEMINI_API_KEY"]
#         if api_key:
#             return api_key
#     except Exception:
#         api_key = None  # no secrets.toml or key missing

#     # 2) Fallback to environment variable
#     api_key = os.getenv("GEMINI_API_KEY")
#     if api_key:
#         return api_key

#     # 3) Fallback to config.json (same folder / working dir)
#     if os.path.exists(CONFIG_PATH):
#         try:
#             with open(CONFIG_PATH, "r", encoding="utf-8") as f:
#                 config = json.load(f)
#             api_key = config.get("GEMINI_API_KEY", "")
#             if api_key:
#                 return api_key
#         except Exception:
#             pass  # if config.json is unreadable or malformed, just ignore

#     # 4) Nothing found
#     return ""


def load_api_key() -> str:
    """Load Gemini API key from Streamlit secrets or environment variable."""
    # 1) Try Streamlit secrets (catch if secrets.toml doesn't exist)
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        if api_key:
            return api_key
    except Exception:
        api_key = None  # no secrets.toml or key missing

    # 2) Fallback to environment variable
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key

    # 3) Nothing found
    return ""


def _blank_minutes():
    return {
        "summary": "",
        "key_points": [],
        "decisions": [],
        "action_items": [],
        "risks_open_questions": []
    }


@st.cache_resource(show_spinner=False)
def get_genai_client(api_key: str):
    if not api_key:
        raise ValueError(
            "No Gemini API key found. Use config.json, an environment variable, "
            "or Streamlit secrets to provide GEMINI_API_KEY."
        )
    return genai.Client(api_key=api_key)


def summarize_meeting(client: genai.Client, transcript: str) -> dict:
    system_instruction = (
        "You are an AI meeting assistant. Read the meeting transcript and "
        "produce ONLY a JSON object with this schema:\n"
        "{\n"
        '  \"summary\": \"short paragraph\",\n'
        '  \"key_points\": [\"point 1\", \"point 2\"],\n'
        '  \"decisions\": [\"decision 1\", \"decision 2\"],\n'
        '  \"action_items\": [\n'
        '    {\n'
        '      \"owner\": \"Name\",\n'
        '      \"task\": \"what to do\",\n'
        '      \"due\": \"deadline or empty string\",\n'
        '      \"priority\": \"High | Medium | Low\"\n'
        '    }\n'
        "  ],\n"
        '  \"risks_open_questions\": [\n'
        '    \"risk or open question 1\",\n'
        '    \"risk or open question 2\"\n'
        "  ]\n"
        "}\n"
        "Rules:\n"
        "1) Always return valid JSON.\n"
        "2) Do not include any extra text before or after the JSON.\n"
        "3) Infer reasonable owners, due dates (or \"\" if none), and priorities "
        "for the action_items based on the transcript.\n"
        "4) Include both risks and open questions together in 'risks_open_questions'."
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            {
                "role": "user",
                "parts": [
                    {"text": system_instruction},
                    {"text": f"Meeting transcript:\n{transcript}"},
                ],
            },
        ],
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    raw_text = response.text
    try:
        parsed = json.loads(raw_text)
        return {**_blank_minutes(), **parsed}
    except json.JSONDecodeError:
        return {"raw_response": raw_text}


def format_action_item(item: dict) -> str:
    owner = item.get("owner", "Unassigned")
    task = item.get("task", "Task not specified")
    due = item.get("due")
    priority = item.get("priority")

    parts = [f"**{owner}** — {task}"]
    if due:
        parts.append(f"**Due:** {due}")
    if priority:
        parts.append(f"**Priority:** {priority}")
    return " | ".join(parts)


# -------------------------- Streamlit UI --------------------------

st.set_page_config(page_title="ClarifyMeet AI", page_icon="🗒️", layout="centered")

st.markdown(
    """
    <style>
        .main {
            background-color: #fafbfc;
        }
        .block-container {
            max-width: 650px;
            margin: auto;
            border-radius: 16px;
            background: #fff;
            box-shadow: 0 2px 16px rgba(0,0,0,0.07);
            padding: 2.5rem 2rem 2rem 2rem;
        }
        .stTextInput>div>div>input, .stTextArea>div>textarea {
            background: #f7f7f7;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }
        .stButton>button {
            width: 100%;
            background: #fff;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            font-weight: 600;
            font-size: 1.1rem;
            margin-top: 0.5rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            justify-content: flex-start;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 1.1rem;
            font-weight: 600;
        }
        .custom-btn-row {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    "<h2 style='text-align: center; margin-bottom: 0.2em;'>ClarifyMeet AI</h2>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='text-align: center; color: #888; margin-bottom: 1.5em;'>Turn Conversations into Clear Actions</div>",
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader("Upload transcript file", type=["txt"], label_visibility="collapsed")
default_text = uploaded_file.read().decode("utf-8") if uploaded_file else ""
transcript = st.text_area(
    "Paste your meeting transcript here",
    value=default_text,
    height=160,
    label_visibility="collapsed",
)

if "minutes" not in st.session_state:
    st.session_state.minutes = _blank_minutes()
if "raw_json" not in st.session_state:
    st.session_state.raw_json = ""
if "raw_response" not in st.session_state:
    st.session_state.raw_response = ""

generate_clicked = st.button("Generate Minutes")

api_key = load_api_key()

if generate_clicked:
    if not transcript.strip():
        st.warning("Please provide a transcript before generating minutes.")
    elif not api_key:
        st.error(
            "No Gemini API key found. Provide it via config.json, the environment, "
            "or Streamlit secrets."
        )
    else:
        with st.spinner("Analyzing meeting..."):
            try:
                client = get_genai_client(api_key)
                summary = summarize_meeting(client, transcript.strip())

                if "raw_response" in summary:
                    st.error("Model returned malformed JSON. See raw output below.")
                    st.session_state.raw_response = summary["raw_response"]
                    st.session_state.raw_json = ""
                else:
                    st.session_state.minutes = summary
                    st.session_state.raw_json = json.dumps(
                        summary, indent=2, ensure_ascii=False
                    )
                    st.session_state.raw_response = ""
                    st.success("Minutes generated successfully!")
            except Exception as exc:
                st.error(f"Failed to generate minutes: {exc}")

tabs = st.tabs(TAB_NAMES)

with tabs[0]:
    summary_text = st.session_state.minutes.get("summary", "")
    key_points = st.session_state.minutes.get("key_points", [])
    if summary_text:
        st.markdown(f"<p style='color:#333;'>{summary_text}</p>", unsafe_allow_html=True)
    if key_points:
        st.markdown(
            "<ul style='margin-top: 1em; color: #555;'>"
            + "".join([f"<li>{point}</li>" for point in key_points])
            + "</ul>",
            unsafe_allow_html=True,
        )
    if not summary_text and not key_points:
        st.markdown(
            "<div style='color: #bbb; margin-top: 1em;'>No data to display.</div>",
            unsafe_allow_html=True,
        )

with tabs[1]:
    actions = st.session_state.minutes.get("action_items", [])
    if actions:
        st.markdown(
            "<ul style='margin-top: 1em; color: #555;'>"
            + "".join([f"<li>{format_action_item(item)}</li>" for item in actions])
            + "</ul>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color: #bbb; margin-top: 1em;'>No action items to display.</div>",
            unsafe_allow_html=True,
        )

with tabs[2]:
    decisions = st.session_state.minutes.get("decisions", [])
    if decisions:
        st.markdown(
            "<ul style='margin-top: 1em; color: #555;'>"
            + "".join([f"<li>{decision}</li>" for decision in decisions])
            + "</ul>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color: #bbb; margin-top: 1em;'>No decisions to display.</div>",
            unsafe_allow_html=True,
        )

with tabs[3]:
    risks = st.session_state.minutes.get("risks_open_questions", [])
    if risks:
        st.markdown(
            "<ul style='margin-top: 1em; color: #555;'>"
            + "".join([f"<li>{risk}</li>" for risk in risks])
            + "</ul>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color: #bbb; margin-top: 1em;'>No risks or open questions to display.</div>",
            unsafe_allow_html=True,
        )

st.markdown('<div class="custom-btn-row">', unsafe_allow_html=True)
copy_col, download_col, clear_col = st.columns(3)

with copy_col:
    if st.button("📋 Copy JSON"):
        if st.session_state.raw_json:
            st.code(st.session_state.raw_json, language="json")
        else:
            st.info("Generate minutes first to view JSON.")

with download_col:
    st.download_button(
        label="⬇️ Download JSON",
        data=json.dumps(st.session_state.minutes, indent=2, ensure_ascii=False),
        file_name="minutes.json",
        mime="application/json",
        disabled=(
            not st.session_state.minutes.get("summary")
            and not st.session_state.minutes.get("action_items")
        ),
    )

with clear_col:
    if st.button("🗑️ Clear Screen"):
        st.session_state.minutes = _blank_minutes()
        st.session_state.raw_json = ""
        st.session_state.raw_response = ""
        st.experimental_rerun()

st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.raw_response:
    with st.expander("Model raw output"):
        st.code(st.session_state.raw_response, language="json")
