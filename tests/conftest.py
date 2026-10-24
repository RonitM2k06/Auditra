import os
import tempfile

# Point the app at a throwaway database before backend modules are imported,
# so test runs never write fixtures into the demo workspace in auditra.db.
_db_dir = tempfile.mkdtemp(prefix="auditra-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_db_dir, 'test.db')}"
