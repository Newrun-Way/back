# app/services/llm/llm_service.py

from typing import List, Optional
from openai import OpenAI
from app.core.config import get_settings


class LLMService:
    """
    GPT API 호출 전담 계층.
    - OpenAI 클라이언트 초기화
    - 기본 모델/temperature/max_tokens 설정
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        settings = get_settings()

        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

        self.model = model or getattr(settings, "DEFAULT_LLM_MODEL", "gpt-4o-mini")
        self.temperature = (
            temperature if temperature is not None
            else getattr(settings, "LLM_TEMPERATURE", 0.2)
        )
        self.max_tokens = (
            max_tokens if max_tokens is not None
            else getattr(settings, "LLM_MAX_TOKENS", 1024)
        )

        self.client = OpenAI(api_key=self.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        system + user 프롬프트를 받아 답변 텍스트만 리턴
        """
        res = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return res.choices[0].message.content

    def simple(self, prompt: str) -> str:
        """
        시스템 프롬프트 없이 단일 user 메시지만 보낼 때
        """
        res = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return res.choices[0].message.content


class LLMGenerator:
    """
    - RAG용 프롬프트 템플릿
    - Chat Memory 기반 템플릿
    - 단순 호출 Wrapper
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        # 기존 코드가 넘기던 인자(api_key, model, temperature, max_tokens)를 그대로 받아서
        # 내부 LLMService에 그대로 전달
        self.llm = LLMService(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # -----------------------------
    # 1) 문서 RAG 템플릿
    # -----------------------------
    def generate_rag_answer(
        self,
        query: str,
        context_chunks: List[str],
        system_prompt: Optional[str] = None,
    ) -> str:
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
    # 2) 대화 기반 RAG 템플릿
    # -----------------------------
    def generate_chat_answer(
        self,
        summary: str,
        recent_turns: str,
        rag_context: str,
        message: str,
        system_prompt: Optional[str] = None,
    ) -> str:
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
    # 3) 단순 호출
    # -----------------------------
    def simple(self, prompt: str) -> str:
        return self.llm.simple(prompt)
