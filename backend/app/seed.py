"""Development seed data: python -m app.seed  (idempotent; safe to re-run)."""
import logging
from decimal import Decimal
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.ai.embeddings.service import reindex_all
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.categories.models import Category
from app.modules.inventory.models import Inventory
from app.modules.products.models import Product, ProductImage, ProductVariant, SellerListing
from app.modules.reviews.models import Review
from app.modules.sellers.models import Seller
from app.modules.users.models import User, UserAddress

log = logging.getLogger("seed")

# (name, brand, description, specs, [(sku, variant, price, qty)])
LAPTOPS = [
    ("Lenovo ThinkPad E14 Gen 5", "Lenovo", "Business laptop with a sturdy build, excellent keyboard and long battery backup. Great for programming and office work.",
     {"ram_gb": 16, "storage_gb": 512, "weight_kg": 1.41, "battery_hours": 12, "processor": "Intel Core i5-1335U", "display": '14" FHD'}, [("TP-E14-16-512", "16GB / 512GB SSD", 62990, 14)]),
    ("Lenovo IdeaPad Slim 3", "Lenovo", "Affordable everyday laptop for students and light work, with a slim profile.",
     {"ram_gb": 8, "storage_gb": 512, "weight_kg": 1.62, "battery_hours": 8, "processor": "AMD Ryzen 5 7520U", "display": '15.6" FHD'}, [("IP-S3-8-512", "8GB / 512GB SSD", 38990, 25)]),
    ("ASUS Vivobook 15", "ASUS", "Reliable 15-inch laptop with a spacious display, suitable for coding, browsing and streaming.",
     {"ram_gb": 16, "storage_gb": 512, "weight_kg": 1.7, "battery_hours": 8, "processor": "Intel Core i5-13500H", "display": '15.6" FHD'}, [("VB-15-16-512", "16GB / 512GB SSD", 54990, 9)]),
    ("HP Pavilion Aero 13", "HP", "Ultra-lightweight magnesium-alloy laptop under 1 kg. Powerful notebook for software development on the go with good battery life.",
     {"ram_gb": 16, "storage_gb": 512, "weight_kg": 0.99, "battery_hours": 10, "processor": "AMD Ryzen 7 7735U", "display": '13.3" 2.5K'}, [("PA-13-16-512", "16GB / 512GB SSD", 68500, 6)]),
    ("Dell Inspiron 14", "Dell", "Well-rounded 14-inch laptop with 1TB storage for developers and creators.",
     {"ram_gb": 16, "storage_gb": 1024, "weight_kg": 1.54, "battery_hours": 9, "processor": "Intel Core i7-1355U", "display": '14" FHD+'}, [("INS-14-16-1TB", "16GB / 1TB SSD", 72990, 7)]),
    ("Apple MacBook Air M2", "Apple", "Thin and light laptop with all-day battery life and silent fanless design.",
     {"ram_gb": 8, "storage_gb": 256, "weight_kg": 1.24, "battery_hours": 18, "processor": "Apple M2", "display": '13.6" Liquid Retina'}, [("MBA-M2-8-256", "8GB / 256GB", 89990, 5)]),
    ("ASUS ROG Strix G16", "ASUS", "High-performance gaming laptop with a dedicated RTX GPU and a 165Hz display. Heavy but powerful.",
     {"ram_gb": 16, "storage_gb": 1024, "weight_kg": 2.5, "battery_hours": 5, "processor": "Intel Core i7-13650HX", "display": '16" QHD 165Hz'}, [("ROG-G16-16-1TB", "16GB / 1TB SSD", 124990, 3)]),
    ("Acer Aspire Lite 14", "Acer", "Budget-friendly lightweight laptop that handles coding and office workloads.",
     {"ram_gb": 16, "storage_gb": 512, "weight_kg": 1.4, "battery_hours": 9, "processor": "Intel Core i5-1235U", "display": '14" FHD'}, [("AL-14-16-512", "16GB / 512GB SSD", 44990, 0)]),
]
PHONES = [
    ("Samsung Galaxy M35 5G", "Samsung", "Smartphone with a big 6000mAh battery for two-day backup and a bright AMOLED display.",
     {"ram_gb": 8, "storage_gb": 128, "battery_mah": 6000, "display": '6.6" AMOLED'}, [("GM35-8-128", "8GB / 128GB", 19999, 40)]),
    ("Redmi Note 13 Pro", "Xiaomi", "200MP camera smartphone with fast charging and an AMOLED display.",
     {"ram_gb": 8, "storage_gb": 256, "battery_mah": 5100, "display": '6.67" AMOLED'}, [("RN13P-8-256", "8GB / 256GB", 25999, 30)]),
    ("OnePlus Nord CE4", "OnePlus", "Smooth performance smartphone with 100W fast charging.",
     {"ram_gb": 8, "storage_gb": 128, "battery_mah": 5500, "display": '6.7" AMOLED'}, [("NCE4-8-128", "8GB / 128GB", 24999, 18)]),
    ("Apple iPhone 15", "Apple", "Premium smartphone with a superb camera system and Dynamic Island.",
     {"ram_gb": 6, "storage_gb": 128, "battery_mah": 3349, "display": '6.1" OLED'}, [("IP15-128", "128GB", 69900, 10)]),
]
HEADPHONES = [
    ("Sony WH-1000XM5", "Sony", "Industry-leading noise cancelling over-ear wireless headphones with 30-hour battery.",
     {"type": "over-ear", "battery_hours": 30, "noise_cancelling": True}, [("WH1000XM5-BLK", "Black", 26990, 12)]),
    ("boAt Rockerz 450", "boAt", "Budget wireless on-ear headphones with deep bass and 15-hour playback.",
     {"type": "on-ear", "battery_hours": 15, "noise_cancelling": False}, [("ROCK450-BLK", "Black", 1499, 100)]),
    ("JBL Tune 760NC", "JBL", "Lightweight wireless headphones with active noise cancelling and 50-hour battery.",
     {"type": "over-ear", "battery_hours": 50, "noise_cancelling": True}, [("T760NC-BLU", "Blue", 5999, 22)]),
]
KITCHEN = [
    ("Philips Air Fryer HD9200", "Philips", "4.1 litre air fryer for healthy oil-free cooking with rapid air technology.",
     {"capacity_l": 4.1, "power_w": 1400}, [("PH-HD9200", "Black", 6995, 20)]),
    ("Prestige Induction Cooktop PIC 20", "Prestige", "Compact induction cooktop with preset Indian menu options.",
     {"power_w": 2000}, [("PR-PIC20", "Black", 2199, 35)]),
]


def _tee(name, colour, description, material, fit, sleeve, gsm, price, sizes, wicking=False):
    """(name, brand, description, specs, [(sku, size, price, qty)]) in the shape the catalogue seeder expects."""
    specs = {"material": material, "fit": fit, "sleeve": sleeve, "gsm": gsm, "color": colour}
    if wicking:
        specs["moisture_wicking"] = True
    base = "".join(w[0] for w in name.replace("-", " ").split()).upper() + "-" + colour[:3].upper()
    return (f"{name} - {colour}", "Urban Threads", description, specs, [(f"{base}-{size}", size, price, qty) for size, qty in sizes])


STD = [("S", 25), ("M", 40), ("L", 40), ("XL", 15)]
TSHIRTS = [
    _tee("Classic Crew Neck Tee", "Black", "Soft 100% combed cotton crew neck t-shirt for everyday wear. Breathable, pre-shrunk and easy to layer.", "cotton", "regular", "half", 180, 499, STD),
    _tee("Classic Crew Neck Tee", "White", "Soft 100% combed cotton crew neck t-shirt for everyday wear. A clean white basic that goes with everything.", "cotton", "regular", "half", 180, 499, STD),
    _tee("Oversized Drop Shoulder Tee", "Grey", "Heavyweight oversized t-shirt with a relaxed drop-shoulder fit. Thick cotton that keeps its shape, streetwear style.", "cotton", "oversized", "half", 240, 799, [("S", 10), ("M", 30), ("L", 30), ("XL", 0)]),
    _tee("Mountains Graphic Print Tee", "Navy", "Navy cotton t-shirt with a mountain adventure graphic print on the chest. Casual and comfortable for weekends and travel.", "cotton", "regular", "half", 180, 699, STD),
    _tee("Dri-Fit Sports Tee", "Red", "Lightweight quick-dry sports t-shirt that wicks sweat away. Ideal for running, gym workouts and training in hot weather.", "polyester", "regular", "half", 130, 899, STD, wicking=True),
    _tee("Slim Fit Polo T-Shirt", "Olive", "Slim fit polo t-shirt in a stretchy cotton blend with a smart collar. Works for office casuals and outings.", "blend", "slim", "half", 200, 1099, [("S", 12), ("M", 20), ("L", 20), ("XL", 8)]),
    _tee("V-Neck Tee", "Maroon", "Slim fit v-neck t-shirt in light 160 GSM cotton. Soft and cool for warm days, easy to wear under a shirt.", "cotton", "slim", "half", 160, 549, STD),
    _tee("Henley Full Sleeve Tee", "Charcoal", "Full sleeve henley t-shirt with a button placket in a warm cotton blend. A comfortable layer for cooler evenings.", "blend", "regular", "full", 220, 1299, [("S", 8), ("M", 18), ("L", 18), ("XL", 6)]),
]


def seed_tshirts(db: Session) -> int:
    """Adds the t-shirt range (own seller + Fashion > T-Shirts). Safe to re-run: existing products are skipped."""
    owner_user = _get_or_create_user(db, "urban@example.com", "Urban Threads Owner", "Seller@123", "seller")
    owner = _get_or_create_seller(db, owner_user, "Urban Threads", "Everyday t-shirts, polos and activewear.")
    cats = {}
    for name, desc, parent in [("Fashion", "Clothing and apparel", None), ("T-Shirts", "T-shirts, polos and tees", "Fashion")]:
        cat = db.scalar(select(Category).where(Category.name == name))
        if cat is None:
            cat = Category(name=name, description=desc, parent_category_id=cats[parent].id if parent else None)
            db.add(cat)
            db.flush()
        cats[name] = cat

    added = 0
    for name, brand, desc, specs, variants in TSHIRTS:
        if db.scalar(select(Product.id).where(Product.name == name)):
            continue
        product = Product(seller_id=owner.id, category_id=cats["T-Shirts"].id, name=name, brand=brand, description=desc, specifications=specs)
        product.images = [ProductImage(image_url=f"https://placehold.co/600x400/png?text={quote(name)}", is_primary=True)]
        for sku, size, price, _qty in variants:
            variant = ProductVariant(sku=sku, variant_name=f"Size {size}", attributes={"size": size})
            variant.listings = [SellerListing(seller_id=owner.id, selling_price=Decimal(price))]
            product.variants.append(variant)
        db.add(product)
        db.flush()
        for variant, (_, _, _, qty) in zip(product.variants, variants, strict=True):
            db.add(Inventory(seller_listing_id=variant.listings[0].id, available_quantity=qty))
        added += 1
    db.commit()
    log.info("t-shirts: %s added", added)
    return added


def _get_or_create_user(db: Session, email: str, name: str, password: str, role: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(name=name, email=email, password_hash=hash_password(password), role=role)
        db.add(user)
        db.flush()
    return user


def _get_or_create_seller(db: Session, user: User, store: str, description: str) -> Seller:
    seller = db.scalar(select(Seller).where(Seller.user_id == user.id))
    if seller is None:
        seller = Seller(user_id=user.id, store_name=store, store_description=description, approval_status="approved")
        db.add(seller)
        db.flush()
    return seller


def seed(db: Session) -> None:
    _get_or_create_user(db, "admin@example.com", "Admin", "Admin@123", "admin")
    seller_user = _get_or_create_user(db, "seller@example.com", "Tech Hub Owner", "Seller@123", "seller")
    seller2_user = _get_or_create_user(db, "seller2@example.com", "Gadget World Owner", "Seller@123", "seller")
    customer = _get_or_create_user(db, "customer@example.com", "Asha Customer", "Customer@123", "customer")
    seller = _get_or_create_seller(db, seller_user, "Tech Hub", "Laptops, phones and accessories from authorised brands.")
    seller2 = _get_or_create_seller(db, seller2_user, "Gadget World", "Your one-stop gadget store.")
    if not db.scalar(select(UserAddress.id).where(UserAddress.user_id == customer.id)):
        db.add(UserAddress(user_id=customer.id, address_line="12 MG Road", city="Bengaluru", state="Karnataka", country="India", postal_code="560001", is_default=True))

    if db.scalar(select(Product.id).limit(1)):
        log.info("catalogue already seeded")
        db.commit()
        seed_tshirts(db)
        return

    cats = {}
    for name, desc, parent in [
        ("Electronics", "Electronic devices", None), ("Laptops", "Laptops and notebooks", "Electronics"),
        ("Smartphones", "Mobile phones", "Electronics"), ("Headphones", "Headphones and earbuds", "Electronics"),
        ("Home & Kitchen", "Appliances and kitchenware", None),
    ]:
        cat = db.scalar(select(Category).where(Category.name == name)) or Category(name=name, description=desc, parent_category_id=cats[parent].id if parent else None)
        db.add(cat)
        db.flush()
        cats[name] = cat

    owners = [seller, seller2]
    count = 0
    for category, items in [("Laptops", LAPTOPS), ("Smartphones", PHONES), ("Headphones", HEADPHONES), ("Home & Kitchen", KITCHEN)]:
        for name, brand, desc, specs, variants in items:
            owner = owners[(count) % 2] if category != "Laptops" else seller
            product = Product(seller_id=owner.id, category_id=cats[category].id, name=name, brand=brand, description=desc, specifications=specs)
            product.images = [ProductImage(image_url=f"https://placehold.co/600x400/png?text={quote(name)}", is_primary=True)]
            for sku, vname, price, _qty in variants:
                variant = ProductVariant(sku=sku, variant_name=vname, attributes={})
                variant.listings = [SellerListing(seller_id=owner.id, selling_price=Decimal(price))]
                product.variants.append(variant)
            db.add(product)
            db.flush()
            for variant, (_, _, _, qty) in zip(product.variants, variants):
                db.add(Inventory(seller_listing_id=variant.listings[0].id, available_quantity=qty))
            count += 1

    # Multi-seller demo: a second seller also offers the HP Pavilion Aero at a different price.
    hp_variant = db.scalar(select(ProductVariant).where(ProductVariant.sku == "PA-13-16-512"))
    extra = SellerListing(seller_id=seller2.id, product_variant_id=hp_variant.id, selling_price=Decimal(67900))
    db.add(extra)
    db.flush()
    db.add(Inventory(seller_listing_id=extra.id, available_quantity=4))

    db.flush()
    for name, rating, text in [("ThinkPad E14", 5, "Superb keyboard and battery."), ("HP Pavilion Aero 13", 4, "Feather light, great screen."), ("Sony WH-1000XM5", 5, "Best noise cancelling I've used.")]:
        product = db.scalar(select(Product).where(Product.name.ilike(f"%{name}%")))
        if product:
            db.add(Review(user_id=customer.id, product_id=product.id, rating=rating, review_text=text))
    db.commit()
    log.info("seeded %s products", count)
    seed_tshirts(db)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        seed(db)
        log.info("indexed %s product embeddings", reindex_all(db))


if __name__ == "__main__":
    main()
