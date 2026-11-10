"""Small builders so tests read as scenarios."""
from decimal import Decimal
from itertools import count

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.modules.categories.models import Category
from app.modules.inventory.models import Inventory
from app.modules.products.models import Product, ProductVariant, SellerListing
from app.modules.sellers.models import Seller
from app.modules.users.models import User, UserAddress

_seq = count(1)
PASSWORD = "Passw0rd!x"


def make_user(db: Session, role: str = "customer", email: str | None = None) -> User:
    n = next(_seq)
    user = User(name=f"{role}{n}", email=email or f"{role}{n}@test.dev", password_hash=hash_password(PASSWORD), role=role)
    db.add(user)
    db.commit()
    return user


def auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def make_seller(db: Session, approved: bool = True) -> tuple[User, Seller]:
    user = make_user(db, "seller")
    seller = Seller(user_id=user.id, store_name=f"Store{user.id}", approval_status="approved" if approved else "pending")
    db.add(seller)
    db.commit()
    return user, seller


def make_category(db: Session, name: str = "Laptops", parent: Category | None = None) -> Category:
    cat = Category(name=name, parent_category_id=parent.id if parent else None)
    db.add(cat)
    db.commit()
    return cat


def make_product(
    db: Session,
    seller: Seller,
    category: Category,
    name: str = "Test Laptop",
    price: int = 50000,
    qty: int = 10,
    specs: dict | None = None,
    description: str = "A laptop",
    brand: str | None = "Acme",
) -> tuple[Product, SellerListing]:
    n = next(_seq)
    product = Product(seller_id=seller.id, category_id=category.id, name=name, description=description, brand=brand, specifications=specs or {})
    variant = ProductVariant(sku=f"SKU-{n}", variant_name="Default", attributes={})
    listing = SellerListing(seller_id=seller.id, selling_price=Decimal(price))
    variant.listings = [listing]
    product.variants = [variant]
    db.add(product)
    db.flush()
    db.add(Inventory(seller_listing_id=listing.id, available_quantity=qty))
    db.commit()
    return product, listing


def make_address(db: Session, user: User) -> UserAddress:
    addr = UserAddress(user_id=user.id, address_line="1 Test St", city="Pune", state="MH", country="India", postal_code="411001", is_default=True)
    db.add(addr)
    db.commit()
    return addr
