"""Entry points: `uvicorn app.asgi:app` locally/containers, `app.asgi.handler` on AWS Lambda."""

from mangum import Mangum

from app.main import create_app

app = create_app()
# lifespan="auto": Mangum runs startup once per cold start; the Mongo client then lives for the instance.
handler = Mangum(app, lifespan="auto")
