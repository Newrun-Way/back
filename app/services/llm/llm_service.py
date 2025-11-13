# app/services/llm/llm_service.py

from openai import OpenAI
from app.core.config import get_settings


class LLMService:
    """
    GPT-4o / GPT-4.1 / GPT-o-mini 등 모든 모델 호출 공통 클래스
    """

    def __init__(self, model: str | None = None):
        settings = get_settings()

        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model or settings.DEFAULT_LLM_MODEL

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2):
        """
        기본 ChatCompletion 호출
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
        시스템 프롬프트 없이 단일 메세지만 보낼 때
        """
        res = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return res.choices[0].message["content"]
