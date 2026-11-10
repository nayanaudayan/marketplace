# API Contract (v1) — shared by backend and frontend

Base URL: `/api/v1`. JSON everywhere. Auth: `Authorization: Bearer <access_token>`.
Errors: HTTP status + `{"detail": "message"}` (422 validation: FastAPI default `detail` array).
Money: decimal **strings** such as `"2199.00"` (INR; avoids float rounding; clients parse them, requests may send numbers or strings). `AIProduct.price`, `min_price`, `selling_price`, `unit_price`, `subtotal`, `total`, `total_amount`, `revenue`, `commission_percentage` and `extracted_filters.min_price/max_price` all follow this. Timestamps: ISO-8601 strings. Roles: `customer | seller | admin`.

## Auth
- `POST /auth/register` `{name,email,password,phone?,role:"customer"|"seller"}` -> `AuthResponse`
- `POST /auth/login` `{email,password}` -> `AuthResponse`
- `POST /auth/refresh` `{refresh_token}` -> `AuthResponse` (refresh token is rotated)
- `POST /auth/logout` `{refresh_token}` -> 204
- `GET /auth/me` -> `User`
- `AuthResponse` = `{access_token, refresh_token, token_type:"bearer", user: User}`
- `User` = `{id,name,email,phone,role,status}`

## Users
- `GET /users/addresses` -> `Address[]`; `POST /users/addresses` `{address_line,city,state,country,postal_code,is_default?}` -> `Address`
- `Address` = `{id,address_line,city,state,country,postal_code,is_default}`

## Categories
- `GET /categories` -> `Category[]` `{id,name,description,parent_category_id}`
- `POST /admin/categories` (admin) `{name,description?,parent_category_id?}` -> `Category`

## Products
- `GET /products?q=&category_id=&brand=&min_price=&max_price=&in_stock=&sort_by=relevance|price_asc|price_desc|newest&page=1&page_size=20` -> `{total,page,page_size,items:ProductCard[]}`
- `GET /products/{id}` -> `ProductDetail`
- `POST /products` (seller, approved) `ProductInput` -> `ProductDetail`
- `PUT /products/{id}` (owner seller/admin) partial `{name?,description?,brand?,category_id?,specifications?,status?}` -> `ProductDetail`
- `DELETE /products/{id}` (owner/admin) -> 204 (soft: status=archived)
- `GET /products/{id}/reviews` -> `Review[]`; `POST /products/{id}/reviews` (customer) `{rating:1-5,review_text?}` -> `Review`
- `ProductCard` = `{id,name,brand,description,category_id,category_name,primary_image_url|null,min_price|null,in_stock:boolean,avg_rating|null,review_count}`
- `ProductDetail` = ProductCard + `{specifications:object, status, seller_id, images:[{id,image_url,is_primary}], variants:[{id,sku,variant_name,attributes:object,listings:[{id,seller_id,seller_name,selling_price,available_quantity}]}]}`
- `ProductInput` = `{category_id,name,description,brand?,specifications?:object,image_urls?:string[],variants:[{sku,variant_name,attributes?:object,selling_price,quantity}]}`
- `Review` = `{id,user_id,user_name,product_id,rating,review_text,created_at}`

## Sellers
- `POST /sellers/register` (customer/seller user) `{store_name,store_description?}` -> `Seller`
- `GET /sellers/profile` -> `Seller`; `PUT /sellers/profile` `{store_name?,store_description?}` -> `Seller`
- `GET /sellers/products` -> `ProductDetail[]` (own products)
- `GET /sellers/orders` -> `SellerOrderItem[]` `{order_id,order_number,order_status,product_name,quantity,subtotal,created_at}`
- `PUT /sellers/listings/{listing_id}` `{selling_price?,available_quantity?}` -> 200 `{id,selling_price,available_quantity}`
- `PUT /sellers/orders/{order_id}/status` `{order_status:"shipped"|"delivered"}` -> `Order`
- `Seller` = `{id,user_id,store_name,store_description,approval_status:"pending"|"approved"|"rejected",commission_percentage}`

## Cart
- `GET /cart` -> `{items:CartItem[],total}`
- `POST /cart/items` `{seller_listing_id,quantity}` -> `Cart`; `PUT /cart/items/{id}` `{quantity}` -> `Cart`; `DELETE /cart/items/{id}` -> `Cart`
- `CartItem` = `{id,seller_listing_id,product_id,product_name,variant_name,seller_name,image_url|null,unit_price,quantity,available_quantity,subtotal}`

## Wishlist
- `GET /wishlist` -> `ProductCard[]`; `POST /wishlist/{product_id}` -> 204; `DELETE /wishlist/{product_id}` -> 204

## Orders & Payments
- `POST /orders` `{shipping_address_id, idempotency_key?}` -> `Order` (from current cart; reserves inventory; status `pending`, payment `pending`)
- `GET /orders` -> `Order[]`; `GET /orders/{id}` -> `Order`; `POST /orders/{id}/cancel` -> `Order`
- `POST /payments/orders/{order_id}/initiate` -> `{payment_id,provider:"mock",status:"pending",amount}`
- `POST /payments/mock/{payment_id}/complete` `{success:boolean}` -> `Order` (dev gateway simulator; calls the same verified path as the webhook)
- `POST /payments/webhook` (HMAC-SHA256 signature in `X-Signature`) -> 200
- `Order` = `{id,order_number,total_amount,payment_status:"pending"|"paid"|"failed"|"refunded",order_status:"pending"|"confirmed"|"shipped"|"delivered"|"cancelled",shipping_address_id,created_at,items:[{id,seller_listing_id,product_name_snapshot,price_snapshot,quantity,subtotal}]}`

## AI
- `POST /ai/search` `{query,filters?:{category?,max_price?,min_price?,minimum_ram_gb?,brand?},conversation_id?,sort_by?:"relevance",page?,page_size?}` -> `AISearchResponse`
- `AISearchResponse` = `{query,conversation_id,extracted_filters:object,total,explanation:string,products:AIProduct[]}`
  `extracted_filters` holds `category, brand, min_price, max_price, usage, keywords` plus two arrays of ready-to-display phrases built from the listings' real spec fields: `specs` (hard requirements, e.g. `"RAM ≥ 16 GB"`, `"Weight ≤ 1.5 kg"`, `"Noise cancelling"`; enforced as filters) and `preferences` (soft wishes used only for ranking, e.g. `"Lighter weight"`). `filters.minimum_ram_gb` in the request is kept for convenience and becomes a `ram_gb ≥` spec.
- `AIProduct` = ProductCard + `{listing_id,price,stock,seller_name,score,match_reason}`
- `POST /ai/compare` `{product_ids:number[]}` -> `{products:ProductDetail[],summary:string}`
- `POST /ai/conversations` `{title?}` -> `{id,title,created_at}`; `GET /ai/conversations/{id}` -> same; `GET /ai/conversations/{id}/messages` -> `{id,role,message,created_at}[]`

## Admin (admin only)
- `GET /admin/dashboard` -> `{users,sellers,pending_sellers,products,orders,revenue}`
- `GET /admin/sellers?status=` -> `Seller[]` (+ `user_email`, `user_name`); `PUT /admin/sellers/{id}/approve`, `PUT /admin/sellers/{id}/reject` -> `Seller`
- `GET /admin/orders` -> `Order[]`

## Health
- `GET /api/v1/health` -> `{status:"healthy"}`

## Dev seed accounts (created by `python -m app.seed`)
admin@example.com / Admin@123 · seller@example.com / Seller@123 (approved) · customer@example.com / Customer@123
