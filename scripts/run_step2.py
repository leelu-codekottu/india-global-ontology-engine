"""Run Step 2: Data Commons bootstrap."""
import sys
sys.path.insert(0, ".")

from pipeline import run_step_2_datacommons_bootstrap
result = run_step_2_datacommons_bootstrap()

import json
print(json.dumps(result, indent=2))
