import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import app.models  # noqa: F401  (registers all models)
from app.core.config import settings
from app.modules.admin.router import router as admin_router
from app.modules.ai_search.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.cart.router import router as cart_router
from app.modules.categories.router import router as categories_router
from app.modules.orders.router import router as orders_router
from app.modules.payments.router import router as payments_router
from app.modules.products.router import router as products_router
from app.modules.sellers.router import router as sellers_router
from app.modules.uploads.router import MEDIA_URL, media_app
from app.modules.uploads.router import router as uploads_router
from app.modules.users.router import router as users_router
from app.modules.wishlist.router import router as wishlist_router

log = logging.getLogger("app")

app = FastAPI(title=settings.app_name, version="1.0.0", docs_url="/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
for router in (
    auth_router,
    users_router,
    categories_router,
    products_router,
    sellers_router,
    uploads_router,
    cart_router,
    wishlist_router,
    orders_router,
    payments_router,
    ai_router,
    admin_router,
):
    app.include_router(router, prefix=API_PREFIX)

app.mount(MEDIA_URL, media_app(), name="media")


@app.get(f"{API_PREFIX}/health", tags=["health"])
def health_check():
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # Internal details go to the log only; clients get a generic message.
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
