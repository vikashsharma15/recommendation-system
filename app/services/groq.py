import logging
from typing import List, Dict, Optional
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_groq_explanation(user_interests: List[str], articles: List[Dict]) -> Optional[str]:
    """
    Optional LLM layer — explains why articles were recommended.
    Returns None if GROQ_API_KEY is not set in .env
    """
    if not settings.groq_api_key:
        logger.debug("Groq skipped — GROQ_API_KEY not set in .env")
        return None

    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)

        article_titles = "\n".join(
            [f"- {a['title']} (score: {a['score']})" for a in articles[:5]]
        )
        prompt = f"""User interests: {', '.join(user_interests)}

Top recommended articles:
{article_titles}

In 2-3 sentences, explain why these articles were recommended. Be concise and friendly."""

        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f"Groq explanation failed: {e}")
        return None