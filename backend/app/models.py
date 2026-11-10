"""Imports every model so Base.metadata is complete (used by Alembic, seeding and tests)."""
from app.core.database import Base  # noqa: F401
from app.modules.ai_search.models import AIConversation, AIMessage, ProductEmbedding  # noqa: F401
from app.modules.cart.models import Cart, CartItem  # noqa: F401
from app.modules.categories.models import Category  # noqa: F401
from app.modules.inventory.models import Inventory  # noqa: F401
from app.modules.orders.models import Order, OrderItem  # noqa: F401
from app.modules.payments.models import Payment  # noqa: F401
from app.modules.products.models import Product, ProductImage, ProductVariant, SellerListing  # noqa: F401
from app.modules.reviews.models import Review  # noqa: F401
from app.modules.sellers.models import Seller  # noqa: F401
from app.modules.users.models import RefreshToken, User, UserAddress  # noqa: F401
from app.modules.wishlist.models import WishlistItem  # noqa: F401
