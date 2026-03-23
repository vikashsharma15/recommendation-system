import logging
from typing import List, Dict, Optional

from app.core.config import get_settings
from app.services import cache

logger = logging.getLogger(__name__)
settings = get_settings()


def get_groq_explanation(
    user_id: int,
    user_interests: List[str],
    articles: List[Dict],
) -> Optional[str]:
    """
    Groq LLM se brief explanation — why were these articles recommended.
    
    Cache strategy:
      - Key: groq:user:{id}
      - TTL: 10 min (2x recommendation TTL)
      - Groq call expensive hai (~500ms) — cache zaroori hai
      - Interests change hone par automatically invalidate hoti hai
        (invalidate_user_cache → delete_pattern → groq key bhi delete)
    """
    if not settings.groq_api_key:
        logger.debug("Groq skipped — GROQ_API_KEY not set")
        return None

    if not articles:
        return None

    # Cache check pehle
    cache_key = cache.make_groq_key(user_id)
    cached = cache.get(cache_key)
    if cached:
        logger.info(f"Groq cache HIT user_id={user_id}")
        return cached

    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)

        titles = "\n".join(
            f"- {a['title']} ({a.get('category', 'General')})"
            for a in articles[:5]
        )

        prompt = (
            f"User interests: {', '.join(user_interests)}\n\n"
            f"Top recommended articles:\n{titles}\n\n"
            f"In 1-2 sentences, give a sharp insight about what's trending in these topics today. "
            f"Reference specific article titles where possible. "
            f"Be direct and specific — no generic intros like 'Hi there' or 'It looks like'. "
            f"Start directly with the insight."
        )

        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.4,
        )

        summary = response.choices[0].message.content.strip()

        # Cache for 10 min — Groq calls expensive hain
        cache.set(cache_key, summary, ttl=600)
        logger.info(f"Groq summary generated + cached user_id={user_id}")

        return summary

    except Exception as e:
        logger.warning(f"Groq failed user_id={user_id}: {e}")
        return None