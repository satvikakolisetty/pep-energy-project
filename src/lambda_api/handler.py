from mangum import Mangum
from main import app

# This handler object is the entry point for AWS Lambda.
# Mangum translates API Gateway's event into a standard ASGI request
# that FastAPI can understand, and translates FastAPI's response back.
handler = Mangum(app)