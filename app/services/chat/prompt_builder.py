# app/services/chat/prompt_builder.py

def build_prompt(summary: str, recent_turns, docs, user_message: str):
    recent_text = "\n".join([f"{m['role']}: {d}" for d, m in recent_turns])
    docs_text = "\n".join([f"- {d}" for d in docs])

    prompt = f"""
[대화 요약]
{summary}

[최근 대화]
{recent_text}

[문서 검색 결과]
{docs_text}

아래 사용자 질문을 최우선으로 답하라:

[질문]
{user_message}
"""

    return prompt
