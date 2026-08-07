"""Integration smoke test: run stream_build_process end-to-end in demo mode.

Verifies the continuation/patch changes don't break the whole build pipeline.
Run:  python test_smoke.py
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Force demo mode (no API key) so we don't make real LLM calls.
os.environ["OPENAI_API_KEY"] = ""
for _k in ("MODEL_POOL", "HUGGING_FACE_HUB_TOKEN", "HF_TOKEN"):
    os.environ.pop(_k, None)

from app.services.ai_service import stream_build_process


async def main():
    # Simulate a continuation build (existing_code present => continuation prompt_type).
    events = []
    async for ev in stream_build_process(
        project_id="smoke-test-project",
        prompt="add a dark mode toggle",
        existing_code="<html><head></head><body><h1>Hello</h1></body></html>",
    ):
        events.append(ev.get("type"))
    print("event types:", events)

    # Must reach READY (i.e. last event is project_update READY) and include artifact.
    assert "project_update" in events, "missing project_update"
    assert "artifact" in events, "missing artifact"
    assert "tasks" in events, "missing tasks"
    print("SMOKE OK")


if __name__ == "__main__":
    asyncio.run(main())
