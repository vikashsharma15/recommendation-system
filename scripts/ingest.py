import argparse
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.embedding_service import index_articles
from app.db.database import create_tables
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

AG_NEWS_CATEGORIES = {1: "World", 2: "Sports", 3: "Business", 4: "Science/Technology"} # it mapped to kaggle dataset 


def load_ag_news(csv_path: str, max_rows: int) -> list:
    """
    AG News train.csv — some versions have header, some don't.
    Auto-detect and handle both.
    """
    peek = pd.read_csv(csv_path, nrows=1, header=None)
    first_val = str(peek.iloc[0, 0]).strip().lower()

    if first_val in ("class index", "class_index"):
        # has header row — skip it
        df = pd.read_csv(csv_path, nrows=max_rows)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    else:
        # no header
        df = pd.read_csv(
            csv_path,
            header=None,
            names=["class_index", "title", "description"],
            nrows=max_rows,
        )

    logger.info(f"AG News — {len(df)} rows. Sample: {df.iloc[0].to_dict()}")

    articles = []
    for idx, row in df.iterrows():
        title = str(row.get("title", "")).strip().strip('"')
        description = str(row.get("description", "")).strip().strip('"')
        try:
            category = AG_NEWS_CATEGORIES.get(int(float(str(row.get("class_index", 0)))), "General")
        except (ValueError, TypeError):
            category = "General"

        if not title or not description or title.lower() == "title":
            continue

        articles.append({
            "id": f"article_{idx}",
            "title": title[:200],
            "description": description[:500],
            "category": category,
        })

    return articles


def detect_and_load(csv_path: str, max_rows: int) -> list:
    """Peek at first row to decide format, then load accordingly."""
    peek = pd.read_csv(csv_path, nrows=1, header=None)
    first_val = str(peek.iloc[0, 0]).strip().lower()
    first_row_cols = [str(c).strip().lower() for c in peek.iloc[0].tolist()]

    logger.info(f"First row values: {first_row_cols}")

    # AG News detection
    if first_val in ("class index", "class_index") or first_val.isdigit() or first_val in ("1","2","3","4"):
        logger.info("Detected: AG News")
        return load_ag_news(csv_path, max_rows)

    # Load with header for other formats
    df = pd.read_csv(csv_path, nrows=max_rows)
    df.columns = [c.strip().lower() for c in df.columns]

    if "content" in df.columns and "publication" in df.columns:
        logger.info("Detected: All the News")
        articles = []
        for idx, row in df.iterrows():
            title = str(row.get("title", "")).strip()
            content = str(row.get("content", "")).strip()
            description = " ".join(content.split())[:400]
            category = str(row.get("publication", "")).strip()
            if not title or not description or title == "nan":
                continue
            articles.append({
                "id": f"article_{idx}",
                "title": title[:200],
                "description": description[:500],
                "category": category,
            })
        return articles

    elif "headline" in df.columns:
        logger.info("Detected: HuffPost")
        articles = []
        for idx, row in df.iterrows():
            title = str(row.get("headline", "")).strip()
            description = str(row.get("short_description", "")).strip()
            category = str(row.get("category", "")).strip()
            if not title or not description or title == "nan":
                continue
            articles.append({
                "id": f"article_{idx}",
                "title": title[:200],
                "description": description[:500],
                "category": category,
            })
        return articles

    else:
        logger.info("Detected: Generic fallback")
        articles = []
        for idx, row in df.iterrows():
            title = str(row.get("title", row.get("headline", ""))).strip()
            description = str(
                row.get("description", row.get("content", row.get("text", "")))
            ).strip()[:400]
            category = str(row.get("category", row.get("publication", ""))).strip()
            if not title or not description or title == "nan":
                continue
            articles.append({
                "id": f"article_{idx}",
                "title": title[:200],
                "description": description[:500],
                "category": category,
            })
        return articles


def main():
    parser = argparse.ArgumentParser(description="Ingest articles into ChromaDB")
    parser.add_argument("--csv", required=True, help="Path to articles CSV")
    parser.add_argument("--max-rows", type=int, default=5000, help="Max articles to index")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        logger.error(f"CSV file not found: {args.csv}")
        sys.exit(1)

    create_tables()
    os.makedirs("data/chroma", exist_ok=True)

    logger.info(f"Loading: {args.csv} (max {args.max_rows} rows)")
    articles = detect_and_load(args.csv, max_rows=args.max_rows)
    logger.info(f"Parsed {len(articles)} valid articles. Starting embedding + indexing...")

    count = index_articles(articles)
    logger.info(f"Done! {count} new articles indexed into ChromaDB.")


if __name__ == "__main__":
    main()