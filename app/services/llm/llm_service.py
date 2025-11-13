# app/services/llm/llm_service.py

from typing import List, Optional
from openai import OpenAI
from app.core.config import get_settings


# -----------------------------------------------------
# 1) LLM 호출기 (API Client)
# -----------------------------------------------------
class LLMService:
    """
    GPT API 호출 전담 계층.
    프롬프트 구성 역할은 하지 않는다.
    """

    def __init__(self, model: Optional[str] = None):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model or settings.DEFAULT_LLM_MODEL

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        """
        기본 ChatCompletion 호출기
        """
        res = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return res.choices[0].message["content"]

    def simple(self, prompt: str):
        """
        시스템 프롬프트 없이 단일 입력만
        """
        res = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return res.choices[0].message["content"]


# -----------------------------------------------------
# 2) LLMGenerator (프롬프트 템플릿 + 호출기 Wrapper)
# -----------------------------------------------------
class LLMGenerator:
    """
    - RAG용 프롬프트 템플릿
    - Chat Memory 기반 템플릿
    - 단순 호출 Wrapper
    """

    def __init__(self, model: Optional[str] = None):
        self.llm = LLMService(model=model)

    # -----------------------------
    # 문서 RAG 템플릿
    # -----------------------------
    def generate_rag_answer(
        self,
        query: str,
        context_chunks: List[str],
        system_prompt: Optional[str] = None,
    ):
        system_prompt = system_prompt or "문서 기반 RAG Assistant입니다."

        context = "\n\n".join(context_chunks)

        user_prompt = f"""
[문서 기반 컨텍스트]
{context}

[사용자 질문]
{query}

위 자료를 기반으로 정확하고 안전하게 답변해 주세요.
"""
        return self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)

    # -----------------------------
    # 대화 기반 RAG 템플릿
    # -----------------------------
    def generate_chat_answer(
        self,
        summary: str,
        recent_turns: str,
        rag_context: str,
        message: str,
        system_prompt: Optional[str] = None,
    ):
        system_prompt = system_prompt or "기업 문서 기반 지능형 대화 Assistant입니다."

        user_prompt = f"""
[요약 메모리]
{summary}

[최근 대화]
{recent_turns}

[문서 기반 컨텍스트]
{rag_context}

[현재 사용자 메시지]
{message}

위 정보를 종합하여 가장 관련성 높은 답변을 제공하세요.
"""
        return self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)

    # -----------------------------
    # 단순 호출
    # -----------------------------
    def simple(self, prompt: str):
        return self.llm.simple(prompt)
