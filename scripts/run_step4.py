"""Run Step 4: Article extraction pipeline with sample articles."""
import sys
sys.path.insert(0, ".")

from pipeline import run_step_4_article_pipeline
result = run_step_4_article_pipeline(use_sample=True, max_articles=5)

import json
print(json.dumps(result, indent=2))
