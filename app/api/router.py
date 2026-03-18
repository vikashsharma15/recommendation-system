from fastapi import APIRouter
from app.api.v1 import auth, users, recommend, articles

router = APIRouter()

router.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
router.include_router(users.router,     prefix="/users",     tags=["Users"])
router.include_router(recommend.router, prefix="/recommend", tags=["Recommendations"])
router.include_router(articles.router,  prefix="/articles",  tags=["Articles"])


@router.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "article-recommender"}