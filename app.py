from fastapi import FastAPI
from main import rec
from fastapi.openapi.utils import get_openapi
import uvicorn

app = FastAPI()


@app.post("/send_ndi")
async def root():
    rec.rec.send_ndi()
    return '200 OK!'


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Custom title",
        version="2.5.0",
        description="This is a very custom OpenAPI schema",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=4446)
    # uvicorn app:app --port 4446 --reload
