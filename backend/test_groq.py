"""
Full diagnostic — runs the ENTIRE pipeline step by step and prints
the actual exception traceback for the first failing article.
"""
import traceback, sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("STEP 1: Fetching RSS feeds")
print("=" * 60)
try:
    from trending.rss_fetcher import fetch_articles
    articles = fetch_articles()
    print(f"  ✅ Fetched {len(articles)} articles")
    if articles:
        a = articles[0]
        print(f"  Sample title: {a['title'][:80]}")
        print(f"  Sample desc:  {a['description'][:80]}")
        print(f"  Sample region: {a['region']}")
except Exception:
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)
print("STEP 2: Filtering")
print("=" * 60)
try:
    from trending.filter import filter_suspicious
    filtered = filter_suspicious(articles)
    print(f"  ✅ Filtered to {len(filtered)} articles")
except Exception:
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 60)
print("STEP 3: Analyzing FIRST article with Groq")
print("=" * 60)
if filtered:
    article = filtered[0]
    print(f"  Title: {article['title'][:80]}")
    print(f"  Desc:  {article['description'][:100]}")
    try:
        from trending.groq_analyzer import analyze_article
        result = analyze_article(article)
        if result:
            print(f"  ✅ SUCCESS! claim={result['claim'][:60]}, score={result['misleading_score']}")
        else:
            print(f"  ⚠️  Returned None (score below threshold or not misleading)")
    except Exception:
        print("  ❌ EXCEPTION:")
        traceback.print_exc()

print()
print("=" * 60)
print("STEP 4: Testing MongoDB upsert")
print("=" * 60)
try:
    from database.db import get_collection
    col = get_collection()
    print(f"  ✅ MongoDB connected, collection: {col.name}")
    print(f"  Documents in collection: {col.count_documents({})}")
except Exception:
    print("  ❌ MongoDB EXCEPTION:")
    traceback.print_exc()

print()
print("DONE")
