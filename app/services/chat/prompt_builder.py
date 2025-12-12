# app/services/chat/prompt_builder.py

class PromptBuilder:
    def build(self, summary: str, recent_turns, docs, user_message: str, user_context: str = None):
        recent_text = "\n".join([f"{m['role']}: {d}" for d, m in recent_turns])
        docs_text = "\n".join([f"- {d}" for d in docs])

        # user_context가 있다면 포함 (필요 시 로직 추가)
        context_section = ""
        if user_context:
            context_section = f"\n[사용자 정보]\n{user_context}\n"

        prompt = f"""
[대화 요약]
{summary}
{context_section}
[최근 대화]
{recent_text}

[문서 검색 결과]
{docs_text}

아래 사용자 질문을 최우선으로 답하라:

[질문]
{user_message}
"""
        return prompt