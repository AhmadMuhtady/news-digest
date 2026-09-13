"""
app.py — Interactive Gradio UI & Groq LLM Synthesis Engine.
"""

import os
import gradio as gr
from openai import OpenAI
from dotenv import load_dotenv

# Import pipeline stages
from fetch import run_fetch
from dedupe import run_dedupe
from digest import load_deduped_data, generate_llm_prompt

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")


def get_groq_client():
    if not GROQ_KEY:
        return None
    return OpenAI(
        api_key=GROQ_KEY,
        base_url="https://api.groq.com/openai/v1"
    )


def fetch_active_chat_models():
    """Queries Groq API dynamically and filters out non-chat models."""
    client = get_groq_client()
    if not client:
        return ["openai/gpt-oss-120b"]

    try:
        models = client.models.list()
        ignored_keywords = ["whisper", "guard", "orpheus", "embed"]
        chat_models = sorted([
            m.id for m in models.data
            if not any(k in m.id for k in ignored_keywords)
        ])
        return chat_models if chat_models else ["openai/gpt-oss-120b"]
    except Exception as e:
        print(f"Warning: Could not fetch Groq model list dynamically ({e})")
        return ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]


def refresh_pipeline():
    """Executes Stage 1 (Fetch) and Stage 2 (Dedupe) live from the UI."""
    try:
        raw_file, raw_count = run_fetch()
        deduped_file, clean_count, removed_count = run_dedupe(raw_file)
        
        status_msg = f"✅ Pipeline Refreshed!\nLoaded {clean_count} articles ({removed_count} duplicates purged)."
        return status_msg, f"{clean_count} clean articles", deduped_file
    except Exception as e:
        err_msg = f"❌ Pipeline Execution Failed: {str(e)}"
        return err_msg, "Error", "N/A"


def synthesize_briefing(model_choice):
    """Loads current on-disk articles, generates prompt, and streams LLM output."""
    client = get_groq_client()
    if not client:
        yield "⚠️ **Error:** `GROQ_API_KEY` environment variable missing in `.env` file."
        return

    articles, metadata = load_deduped_data()

    if not articles:
        yield "⚠️ **Error:** No clean articles found on disk. Click **'Refresh Pipeline Data'** first."
        return

    sys_prompt, user_payload = generate_llm_prompt(articles)

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_payload}
    ]

    try:
        response = client.chat.completions.create(
            model=model_choice,
            messages=messages,
            temperature=0.2,
            max_tokens=8192,
            stream=True
        )

        full_text = ""
        for chunk in response:
            content = chunk.choices[0].delta.content or ""
            full_text += content
            yield full_text

    except Exception as e:
        yield f"❌ **Groq API Execution Error ({model_choice}):**\n\n```text\n{str(e)}\n```"


def build_ui():
    active_models = fetch_active_chat_models()
    
    articles, metadata = load_deduped_data()
    initial_count = f"{len(articles)} clean articles" if articles else "0 clean articles"
    initial_file = metadata.get("source_raw_file", "None") if metadata else "None"

    with gr.Blocks(title="Middle East News Intelligence", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 📰 Middle East Executive Intelligence Digest")
        gr.Markdown("Automated Pipeline: Fetch ➔ Dedupe ➔ Groq LLM Synthesis")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Pipeline Control")
                
                status_box = gr.Textbox(label="Pipeline Log", value="System Ready.", interactive=False)
                art_count_box = gr.Textbox(label="Active Articles", value=initial_count, interactive=False)
                source_file_box = gr.Textbox(label="Active File", value=initial_file, interactive=False)

                refresh_btn = gr.Button("🔄 Fetch & Dedupe Fresh News", variant="secondary")

                gr.Markdown("---")
                gr.Markdown("### LLM Synthesis")

                model_dropdown = gr.Dropdown(
                    label="Select Active Model",
                    choices=active_models,
                    value="openai/gpt-oss-120b" if "openai/gpt-oss-120b" in active_models else active_models[0],
                    interactive=True
                )

                generate_btn = gr.Button("🚀 Generate Executive Briefing", variant="primary")

            with gr.Column(scale=3):
                output_markdown = gr.Markdown(label="Executive Briefing Output")

        refresh_btn.click(
            fn=refresh_pipeline,
            inputs=[],
            outputs=[status_box, art_count_box, source_file_box]
        )

        generate_btn.click(
            fn=synthesize_briefing,
            inputs=[model_dropdown],
            outputs=[output_markdown]
        )

    return demo


if __name__ == "__main__":
    app = build_ui()
    app.launch(server_name="127.0.0.1", server_port=7860, share=False)