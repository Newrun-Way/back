from typing import List, Dict, Optional, Any
from openai import OpenAI
from loguru import logger

from app.core.config import get_settings


class LLMService:
    """
    OpenAI ChatCompletion 호출을 담당하는 저수준 클라이언트.
    - API 키, 모델, temperature, max_tokens를 설정에서 가져오거나 인자로 덮어쓴다.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        settings = get_settings()

        self.api_key = api_key or getattr(settings, "OPENAI_API_KEY", None)
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

        self.model = model or getattr(settings, "LLM_MODEL", "gpt-4o-mini")
        self.temperature = (
            temperature if temperature is not None
            else getattr(settings, "LLM_TEMPERATURE", 0.7)
        )
        self.max_tokens = (
            max_tokens if max_tokens is not None
            else getattr(settings, "LLM_MAX_TOKENS", 1024)
        )

        self.client = OpenAI(api_key=self.api_key)

        logger.info(f"LLMService 초기화: model={self.model}, temp={self.temperature}")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        system + user 프롬프트를 받아 답변 문자열만 반환.
        """
        logger.info(f"LLM generate 호출: user_prompt 앞부분={user_prompt[:50]!r}")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True, #스트리밍 테스트  
            )
            answer = response.choices[0].message.content

            usage = response.usage
            logger.info(
                "LLM 응답 완료: input=%s tokens, output=%s tokens",
                getattr(usage, "prompt_tokens", None),
                getattr(usage, "completion_tokens", None),
            )
            return answer
        except Exception as e:
            logger.error(f"LLM 호출 실패: {e}")
            return f"답변 생성 중 오류가 발생했습니다: {str(e)}"

    def simple(self, prompt: str) -> str:
        """
        시스템 프롬프트 없이 단일 user 메시지만 보낼 때 사용.
        """
        default_system = "당신은 유용한 AI 어시스턴트입니다."
        return self.generate(default_system, prompt)


class LLMGenerator:
    """
    상위 레벨의 RAG/챗봇용 LLM 래퍼.

    ✅ 기존 코드와 호환되도록 __init__ 시그니처를 맞춤:
        LLMGenerator(
            api_key=...,
            model=...,
            temperature=...,
            max_tokens=...,
            system_prompt=...,
            user_prompt_template=...
        )

    그리고 메서드도 옛날 llm.py처럼:
    - generate(context, question)
    - generate_with_sources(contexts, question)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = "",
        user_prompt_template: Optional[str] = "",
    ):
        settings = get_settings()

        # LLMService 내부 클라이언트 생성
        self.llm = LLMService(
            api_key=api_key,
            model=model or getattr(settings, "LLM_MODEL", "gpt-4o-mini"),
            temperature=temperature if temperature is not None else getattr(settings, "LLM_TEMPERATURE", 0.7),
            max_tokens=max_tokens if max_tokens is not None else getattr(settings, "LLM_MAX_TOKENS", 1024),
        )

        # 프롬프트 템플릿 설정
        self.system_prompt: str = (
            system_prompt if system_prompt
            else getattr(settings, "SYSTEM_PROMPT", "당신은 문서 기반 QA 어시스턴트입니다.")
        )
        self.user_prompt_template: str = (
            user_prompt_template if user_prompt_template
            else getattr(
                settings,
                "USER_PROMPT_TEMPLATE",
                "다음 문서를 참고하여 질문에 답하세요.\n\n{context}\n\n질문: {question}\n답변:",
            )
        )

        logger.info(
            "LLMGenerator 초기화: model=%s, temp=%s", self.llm.model, self.llm.temperature
        )

    def generate(self, context: str, question: str) -> str:
        """
        질문에 대한 답변 생성 (기존 llm.py의 generate와 동일한 인터페이스).
        """
        user_prompt = self.user_prompt_template.format(
            context=context,
            question=question,
        )

        logger.info(f"LLMGenerator.generate 호출: question={question[:50]!r}")
        return self.llm.generate(self.system_prompt, user_prompt)

    def generate_with_sources(
        self,
        contexts: List[Dict[str, Any]],
        question: str,
    ) -> Dict[str, Any]:
        """
        출처 정보를 포함한 답변 생성 (기존 llm.py의 generate_with_sources와 호환).
        contexts: [{"content": str, "metadata": dict, "score": float}, ...]
        """
        # 컨텍스트 포맷팅
        context_parts: List[str] = []
        for i, ctx in enumerate(contexts):
            content = ctx.get("content", "")
            metadata = ctx.get("metadata", {}) or {}
            doc_name = metadata.get("doc_name", "알 수 없음")
            hierarchy_path = metadata.get("hierarchy_path", "")

            header = f"[문서 {i+1}: {doc_name}]"
            if hierarchy_path:
                header += f"\n[위치: {hierarchy_path}]"

            context_parts.append(f"{header}\n{content}")

        context_str = "\n\n".join(context_parts)

        # 답변 생성
        answer = self.generate(context_str, question)

        # 출처 정보 구성
        sources: List[Dict[str, Any]] = []
        for i, ctx in enumerate(contexts):
            metadata = ctx.get("metadata", {}) or {}
            source_info: Dict[str, Any] = {
                "index": i + 1,
                "doc_name": metadata.get("doc_name", "알 수 없음"),
                "doc_id": metadata.get("doc_id", ""),
                "chunk_id": metadata.get("chunk_id", -1),
                "chunk_index": metadata.get("chunk_index", -1),
                "score": ctx.get("score", 0.0),
                "content_preview": ctx.get("content", "")[:200] + "...",
                # 문서 구조 정보가 있으면 포함
                "chapter_number": metadata.get("chapter_number", ""),
                "chapter_title": metadata.get("chapter_title", ""),
                "article_number": metadata.get("article_number", ""),
                "article_title": metadata.get("article_title", ""),
                "hierarchy_path": metadata.get("hierarchy_path", ""),
                # 사용자/프로젝트 관련 메타 (있으면)
                "user_id": metadata.get("user_id", ""),
                "dept_id": metadata.get("dept_id", ""),
                "project_id": metadata.get("project_id", ""),
            }
            sources.append(source_info)

        return {
            "answer": answer,
            "sources": sources,
            "context_used": context_str,
        }
