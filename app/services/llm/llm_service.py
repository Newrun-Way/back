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
                stream=False, #일반 generate는 stream하지않고 choice를 사용
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

    async def generate_stream(self, system_prompt, user_prompt):
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

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
        #질문에 대한 답변 생성 (기존 llm.py의 generate와 동일한 인터페이스)
        user_prompt = self.user_prompt_template.format(
            context=context,
            question=question,
        )
        logger.info(f"LLMGenerator.generate 호출: question={question[:50]!r}")
        return self.llm.generate(self.system_prompt, user_prompt)

    def generate_with_sources(
        self,
        contexts: list,
        question: str,
        table_service=None,
        table_processor=None,
    ):
        """
        contexts: retriever 결과
        table_processor.get_table(file_path, table_id)를 호출하도록 구조 변경
        """

        final_sources = []
        context_parts = []

        for idx, ctx in enumerate(contexts, start=1):
            content = ctx.get("content", "")
            meta = ctx.get("metadata", {})
            score = ctx.get("score", 0.0)

            file_path = meta.get("file_path")  # 반드시 존재
            table_id = meta.get("table_id")
            doc_name = meta.get("filename") or meta.get("external_doc_id")

            table_json = None
            if table_id and table_processor:
                table_json = table_processor.get_table(file_path, table_id)

            # 표가 있다면 LLM context에 추가
            if table_json:
                content += f"\n\n[표 {table_id} 데이터]\n{json.dumps(table_json, ensure_ascii=False, indent=2)}"
            else:
                if meta.get("type") == "table":
                    content += f"\n\n(표 {table_id} 데이터를 찾을 수 없습니다)"

            # LLM 문맥 구성
            context_parts.append(
                f"[{doc_name}]\n"
                f"[위치: {file_path}]\n"
                f"{content}\n"
            )

            final_sources.append({
                "index": idx,
                "doc_name": doc_name,
                "doc_id": meta.get("db_id", ""),
                "chunk_id": meta.get("chunk_id", -1),
                "score": score,
                "type": meta.get("type"),
                "table_id": table_id,
            })

        context_used = "\n".join(context_parts)

        answer = self.generate(question, context_used)

        return {
            "answer": answer,
            "sources": final_sources,
            "context_used": context_used,
        }

    async def generate_stream(self, context: str, question: str):
        user_prompt = self.user_prompt_template.format(
            context=context,
            question=question,
        )

        async for tok in self.llm.generate_stream(self.system_prompt, user_prompt):
            yield tok
