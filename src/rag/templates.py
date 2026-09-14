"""Approved SQL template library for the `orders` table.

Every template is a complete, read-only PostgreSQL query using real columns only.
Templates are intentionally *unfiltered* (no WHERE on a specific city/brand/date);
questions that mention such a value are routed to Gemini by the compatibility guard.

Lightweight metadata per template (used by src/agent/routing.py):
  intent          sum | count | avg | ranking | trend | share | growth | comparison
  dimensions      GROUP BY axes the result is broken down by
                  (city, brand_name, category_level1, order_items_name, customer_name,
                   gender, month, day, year, weekday, discount_status)
  metrics         measures the template reports (revenue, orders, customers, quantity,
                  discount, share, growth, revenue_per_unit)
  filters         WHERE predicates baked into the SQL (never a specific city/brand/date value)
  time_filter     None for every template: no template is restricted to a date window
  supports_top_n  True when "top N" wording can safely be applied by rewriting LIMIT
"""
from typing import Dict, List

SQL_TEMPLATES: List[Dict] = [
    # ------------------------------------------------------------- scalars
    {
        "id": "total_revenue",
        "description": "Total revenue of all orders",
        "example_questions": [
            "مجموع فروش کل چقدره؟", "کل درآمد چقدر است؟", "جمع کل فروش", "مجموع درآمد کل فروشگاه",
            "فروش کل چقدر بوده؟", "Total revenue", "What is the total sales?", "Sum of all revenue",
            "Overall sales amount", "Total sales so far",
        ],
        "sql": 'SELECT SUM("revenue") AS total_revenue FROM "orders"',
        "intent": "sum", "dimensions": [], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
    {
        "id": "order_count",
        "description": "Number of distinct orders",
        "example_questions": [
            "تعداد کل سفارشات چندتا است؟", "چند سفارش ثبت شده؟", "تعداد کل سفارش ها", "آمار تعداد سفارش ها",
            "چند خرید انجام شده است؟", "How many orders exist?", "Total order count", "Number of all orders",
            "Count all orders", "How many purchases were made?",
        ],
        "sql": 'SELECT COUNT(DISTINCT "order_id") AS total_orders FROM "orders"',
        "intent": "count", "dimensions": [], "metrics": ["orders"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
    {
        "id": "unique_customers",
        "description": "Number of distinct customers",
        "example_questions": [
            "تعداد مشتریان منحصر به فرد", "چند مشتری یکتا داریم؟", "تعداد کل مشتریان", "چند نفر خرید کرده اند؟",
            "تعداد مشتری های متمایز", "How many unique customers?", "Number of distinct customers",
            "Count of customers", "Unique buyers count", "How many different customers ordered?",
        ],
        "sql": 'SELECT COUNT(DISTINCT "customer_id") AS unique_customers FROM "orders"',
        "intent": "count", "dimensions": [], "metrics": ["customers"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
    {
        "id": "average_order_value",
        "description": "Average revenue per order line (rounded)",
        "example_questions": [
            "میانگین ارزش هر سفارش چقدره؟", "میانگین مبلغ خرید مشتریان", "میانگین درآمد هر سفارش",
            "متوسط ارزش سبد خرید", "هر سفارش به طور میانگین چقدر درآمد دارد؟", "Average order value",
            "Average basket size", "Average purchase amount", "Mean order value", "What is the average revenue per order?",
        ],
        "sql": 'SELECT ROUND(AVG("revenue"), 0) AS avg_order_value FROM "orders"',
        "intent": "avg", "dimensions": [], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
    {
        "id": "average_discount",
        "description": "Average applied discount (only rows with a discount)",
        "example_questions": [
            "میانگین تخفیف اعمال شده", "میانگین تخفیف چقدر است؟", "متوسط میزان تخفیف", "میانگین تخفیف هر سفارش",
            "به طور میانگین چقدر تخفیف داده شده؟", "Average discount", "Mean discount amount",
            "Average discount per order", "What is the average discount value?", "Typical discount amount",
        ],
        "sql": 'SELECT ROUND(AVG("discount_amount"), 0) AS avg_discount FROM "orders" WHERE "discount_amount" > 0',
        "intent": "avg", "dimensions": [], "metrics": ["discount"], "filters": ['"discount_amount" > 0'],
        "time_filter": None, "supports_top_n": False,
    },
    # ------------------------------------------------------------- category
    {
        "id": "revenue_by_category",
        "description": "Revenue per main category (category_level1), highest first",
        "example_questions": [
            "فروش هر دسته اصلی", "فروش هر دسته اصلی (Category_Level1)", "مجموع فروش هر دسته بندی چقدر است؟",
            "درآمد هر کتگوری را نشان بده", "کدام دسته بندی بیشترین فروش را دارد؟", "فروش به تفکیک دسته بندی",
            "دسته بندی های با بیشترین درآمد", "پرفروش ترین دسته بندی ها", "رتبه بندی دسته بندی ها بر اساس درآمد",
            "Revenue by category", "Sales by category_level1", "Which category has highest revenue?",
            "Top categories by sales", "Category revenue ranking", "Sales performance by category",
        ],
        "sql": 'SELECT "category_level1", SUM("revenue") AS revenue FROM "orders" GROUP BY "category_level1" ORDER BY revenue DESC',
        "intent": "ranking", "dimensions": ["category_level1"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "quantity_by_category",
        "description": "Sold quantity per main category",
        "example_questions": [
            "تعداد فروش هر دسته بندی چقدر بوده؟", "تعداد کالای فروخته شده در هر کتگوری", "حجم فروش هر دسته بندی",
            "Total quantity sold per category", "Units sold by category", "Quantity per category_level1",
        ],
        "sql": 'SELECT "category_level1", SUM("quantity") AS total_qty FROM "orders" GROUP BY "category_level1" ORDER BY total_qty DESC',
        "intent": "ranking", "dimensions": ["category_level1"], "metrics": ["quantity"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "category_share",
        "description": "Each category's share of total revenue",
        "example_questions": [
            "سهم هر دسته بندی از درآمد", "درصد فروش هر کتگوری", "تحلیل سهم دسته بندی ها", "سهم درآمدی هر دسته بندی",
            "هر کتگوری چه سهمی از فروش دارد؟", "Category revenue share", "Revenue contribution per category",
            "Category market share", "Share of each category in total revenue", "Category contribution analysis",
        ],
        "sql": (
            'SELECT "category_level1", SUM("revenue") AS revenue, '
            'ROUND(100.0 * SUM("revenue") / SUM(SUM("revenue")) OVER (), 2) AS revenue_share_pct '
            'FROM "orders" GROUP BY "category_level1" ORDER BY revenue DESC'
        ),
        "intent": "share", "dimensions": ["category_level1"], "metrics": ["revenue", "share"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "high_revenue_low_quantity",
        "description": "Categories with high revenue relative to quantity (premium categories)",
        "example_questions": [
            "دسته بندی های با درآمد بالا و تعداد فروش کم", "کدام کتگوری درآمد بالا ولی فروش کم دارد؟",
            "دسته بندی های کم فروش اما پردرآمد", "محصولات پریمیوم با تعداد فروش کم", "درآمد به ازای هر واحد در هر دسته",
            "High revenue low quantity categories", "Premium categories with low order quantity",
            "Revenue per unit by category", "Most profitable low quantity categories",
        ],
        "sql": (
            'SELECT "category_level1", SUM("revenue") AS revenue, SUM("quantity") AS qty, '
            'ROUND(SUM("revenue") / NULLIF(SUM("quantity"), 0), 0) AS revenue_per_unit '
            'FROM "orders" GROUP BY "category_level1" ORDER BY revenue_per_unit DESC'
        ),
        "intent": "ranking", "dimensions": ["category_level1"], "metrics": ["revenue", "quantity", "revenue_per_unit"],
        "filters": [], "time_filter": None, "supports_top_n": True,
    },
    # ------------------------------------------------------------- products
    {
        "id": "top_selling_products",
        "description": "Best-selling products by revenue with sold quantity",
        "example_questions": [
            "تاپ 10 محصول پرفروش", "پرفروش ترین محصولات را نشان بده", "۱۰ محصول برتر فروش",
            "کدام محصولات بیشترین فروش را داشتند؟", "محصولات محبوب مشتریان", "بیشترین فروش مربوط به کدام محصول است؟",
            "Show top 10 products", "Best selling products", "Top products by revenue", "Most popular products",
            "Which products sold the most?",
        ],
        "sql": (
            'SELECT "order_items_name", SUM("quantity") AS total_qty, SUM("revenue") AS revenue '
            'FROM "orders" GROUP BY "order_items_name" ORDER BY revenue DESC LIMIT 10'
        ),
        "intent": "ranking", "dimensions": ["order_items_name"], "metrics": ["revenue", "quantity"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "low_selling_products",
        "description": "Products with the lowest sold quantity",
        "example_questions": [
            "کم فروش ترین محصولات", "محصولات با فروش پایین", "محصولات کم تقاضا", "بدترین محصولات از نظر فروش",
            "محصولات غیرفعال", "کدام محصولات فروش کمی دارند؟", "محصولات با عملکرد ضعیف",
            "Worst selling products", "Low demand products", "Products with lowest sales", "Slow moving products",
            "Least popular products", "Inactive products",
        ],
        "sql": (
            'SELECT "order_items_name", SUM("quantity") AS qty, SUM("revenue") AS revenue '
            'FROM "orders" GROUP BY "order_items_name" ORDER BY qty ASC, revenue ASC LIMIT 20'
        ),
        "intent": "ranking", "dimensions": ["order_items_name"], "metrics": ["quantity", "revenue"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "pareto_products",
        "description": "Products that make up 80% of revenue (Pareto)",
        "example_questions": [
            "محصولات موثر در ۸۰ درصد درآمد", "تحلیل پارتو محصولات", "تحلیل قانون ۸۰/۲۰ فروش", "محصولات کلیدی درآمدزا",
            "Products contributing to 80% revenue", "Pareto analysis of products", "80/20 sales analysis",
            "Important revenue driving products",
        ],
        "sql": (
            'WITH product_revenue AS ('
            '  SELECT "order_items_name", SUM("revenue") AS revenue FROM "orders" GROUP BY "order_items_name"'
            '), ranked AS ('
            '  SELECT "order_items_name", revenue, '
            '         SUM(revenue) OVER (ORDER BY revenue DESC) AS cumulative_revenue, '
            '         SUM(revenue) OVER () AS total_revenue FROM product_revenue'
            ') SELECT "order_items_name", revenue FROM ranked '
            'WHERE cumulative_revenue <= total_revenue * 0.8 ORDER BY revenue DESC LIMIT 100'
        ),
        "intent": "share", "dimensions": ["order_items_name"], "metrics": ["revenue", "share"],
        "filters": ["cumulative_revenue <= 80% of total"], "time_filter": None, "supports_top_n": False,
    },
    {
        "id": "top_products_by_city",
        "description": "Best-selling product in each city",
        "example_questions": [
            "پرفروش ترین محصولات هر شهر", "محبوب ترین محصولات در هر شهر", "کدام محصولات در هر شهر بهتر فروش دارند؟",
            "بهترین محصولات هر شهر", "فروش محصولات به تفکیک شهر", "Best selling products by city",
            "Top products in each city", "Most popular products per city", "City wise best sellers",
        ],
        "sql": (
            'WITH city_products AS ('
            '  SELECT "city", "order_items_name", SUM("quantity") AS qty, SUM("revenue") AS revenue, '
            '         ROW_NUMBER() OVER (PARTITION BY "city" ORDER BY SUM("revenue") DESC) AS rn '
            '  FROM "orders" WHERE "city" IS NOT NULL GROUP BY "city", "order_items_name"'
            ') SELECT "city", "order_items_name", qty, revenue FROM city_products WHERE rn = 1 ORDER BY revenue DESC LIMIT 100'
        ),
        "intent": "ranking", "dimensions": ["city", "order_items_name"], "metrics": ["revenue", "quantity"],
        "filters": ['"city" IS NOT NULL'], "time_filter": None, "supports_top_n": False,
    },
    # ------------------------------------------------------------- brands
    {
        "id": "revenue_by_brand",
        "description": "Revenue per brand, highest first",
        "example_questions": [
            "تاپ 5 برند از نظر فروش", "برندهای برتر", "کدام برند بیشترین فروش را دارد؟", "درآمد برندها را نشان بده",
            "برندهای پرفروش", "بهترین برندها از نظر درآمد", "فروش هر برند", "مقایسه برندها بر اساس درآمد",
            "Top brands", "Best brands by sales", "Revenue by brand", "Brand sales report",
            "Brands with highest revenue", "Top performing brands",
        ],
        "sql": 'SELECT "brand_name", SUM("revenue") AS revenue FROM "orders" GROUP BY "brand_name" ORDER BY revenue DESC LIMIT 20',
        "intent": "ranking", "dimensions": ["brand_name"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    # ------------------------------------------------------------- cities
    {
        "id": "revenue_by_city",
        "description": "Revenue per city, highest first",
        "example_questions": [
            "فروش هر شهر (تاپ 10)", "شهرهای برتر از نظر فروش", "درآمد هر شهر را نشان بده", "کدام شهر بیشترین فروش را دارد؟",
            "فروش بر اساس شهر", "فروش هر شهر", "مقایسه درآمد شهرها", "Top cities by sales", "Revenue by city",
            "Which cities generate most revenue?", "Sales by city", "City revenue analysis",
        ],
        "sql": 'SELECT "city", SUM("revenue") AS revenue FROM "orders" GROUP BY "city" ORDER BY revenue DESC LIMIT 10',
        "intent": "ranking", "dimensions": ["city"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "orders_by_city",
        "description": "Number of distinct orders per city, highest first",
        "example_questions": [
            "تاپ 5 شهر از نظر تعداد سفارش", "تعداد سفارش هر شهر", "کدام شهر بیشترین تعداد سفارش را دارد؟",
            "شهرها بر اساس تعداد سفارش", "پرسفارش ترین شهرها", "Top cities by order count", "Orders per city",
            "Which city has the most orders?", "Number of orders by city", "Cities ranked by order volume",
        ],
        "sql": 'SELECT "city", COUNT(DISTINCT "order_id") AS order_count FROM "orders" GROUP BY "city" ORDER BY order_count DESC LIMIT 10',
        "intent": "ranking", "dimensions": ["city"], "metrics": ["orders"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    # ------------------------------------------------------------- customers
    {
        "id": "top_customers",
        "description": "Customers with the highest total revenue",
        "example_questions": [
            "تاپ 5 مشتری از نظر خرید", "بهترین مشتریان", "مشتریانی با بیشترین خرید", "مشتریان VIP",
            "کدام مشتری بیشترین درآمد ایجاد کرده؟", "مشتریان برتر از نظر فروش", "Top customers",
            "Best customers by revenue", "Highest spending customers", "VIP customers", "Customers generating most revenue",
        ],
        "sql": 'SELECT "customer_name", SUM("revenue") AS total_spent FROM "orders" GROUP BY "customer_name" ORDER BY total_spent DESC LIMIT 20',
        "intent": "ranking", "dimensions": ["customer_name"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "customer_frequency",
        "description": "Customers with the most distinct orders",
        "example_questions": [
            "مشتریان با بیشترین تعداد سفارش", "وفادارترین مشتریان", "کدام مشتری بیشتر سفارش داده است؟", "مشتریان پرتکرار",
            "مشتریانی با خرید مکرر", "Most frequent customers", "Top repeat customers",
            "Customers with highest number of orders", "Who orders the most?", "Most loyal customers",
        ],
        "sql": 'SELECT "customer_name", COUNT(DISTINCT "order_id") AS order_count FROM "orders" GROUP BY "customer_name" ORDER BY order_count DESC LIMIT 20',
        "intent": "ranking", "dimensions": ["customer_name"], "metrics": ["orders"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "revenue_by_gender",
        "description": "Revenue per product gender segment",
        "example_questions": [
            "فروش بر اساس جنسیت", "درآمد مشتریان زن و مرد", "مقایسه فروش بین جنسیت ها", "کدام جنسیت خرید بیشتری دارد؟",
            "تحلیل جنسیت مشتریان", "Revenue by gender", "Sales by gender", "Compare male and female revenue",
            "Customer gender analysis", "Which gender buys more?",
        ],
        "sql": 'SELECT "gender", SUM("revenue") AS revenue FROM "orders" GROUP BY "gender" ORDER BY revenue DESC',
        "intent": "comparison", "dimensions": ["gender"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    # ------------------------------------------------------------- time
    {
        "id": "monthly_sales_trend",
        "description": "Total revenue per month",
        "example_questions": [
            "فروش ماهانه", "روند فروش ماهانه را نشان بده", "گزارش فروش ماه به ماه", "درآمد ماهانه", "نمودار فروش ماهانه را نمایش بده",
            "فروش ماهانه کل", "Monthly sales trend", "Revenue by month", "Monthly revenue report", "Show monthly sales chart",
            "Sales per month",
        ],
        "sql": (
            'SELECT DATE_TRUNC(\'month\', "order_date")::date AS month, SUM("revenue") AS revenue '
            'FROM "orders" GROUP BY 1 ORDER BY month'
        ),
        "intent": "trend", "dimensions": ["month"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
    {
        "id": "revenue_growth_monthly",
        "description": "Month-over-month revenue growth percentage",
        "example_questions": [
            "رشد ماهانه درآمد", "درصد رشد فروش ماه به ماه", "درآمد هر ماه چقدر رشد کرده؟", "تحلیل رشد ماهانه فروش",
            "نرخ رشد ماهانه", "Monthly revenue growth", "Month over month growth rate", "How is revenue growing monthly?",
            "MoM growth percentage", "Revenue increase month by month",
        ],
        "sql": (
            'WITH monthly AS ('
            '  SELECT DATE_TRUNC(\'month\', "order_date")::date AS month, SUM("revenue") AS revenue FROM "orders" GROUP BY 1'
            ') SELECT month, revenue, LAG(revenue) OVER (ORDER BY month) AS prev_revenue, '
            'ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month)) / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 2) AS growth_pct '
            'FROM monthly ORDER BY month'
        ),
        "intent": "growth", "dimensions": ["month"], "metrics": ["revenue", "growth"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
    {
        "id": "daily_sales_trend",
        "description": "Total revenue per day",
        "example_questions": [
            "روند فروش روزانه", "درآمد روزانه را نمایش بده", "گزارش فروش روزانه", "فروش هر روز چقدر بوده؟",
            "Daily sales trend", "Revenue by day", "Daily revenue report", "Show daily sales",
        ],
        "sql": 'SELECT "order_date" AS day, SUM("revenue") AS revenue FROM "orders" GROUP BY "order_date" ORDER BY day',
        "intent": "trend", "dimensions": ["day"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
    {
        "id": "yearly_sales",
        "description": "Total revenue per year",
        "example_questions": [
            "فروش سالانه را نشان بده", "درآمد هر سال چقدر بوده؟", "گزارش فروش سالانه", "مقایسه درآمد سال ها",
            "Revenue by year", "Yearly sales report", "Annual revenue summary", "Compare yearly revenue",
        ],
        "sql": 'SELECT EXTRACT(YEAR FROM "order_date")::int AS year, SUM("revenue") AS revenue FROM "orders" GROUP BY 1 ORDER BY year',
        "intent": "trend", "dimensions": ["year"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
    {
        "id": "revenue_by_weekday",
        "description": "Revenue per weekday (0 = Sunday)",
        "example_questions": [
            "بهترین روز هفته برای فروش", "درآمد بر اساس روز هفته", "کدام روز هفته بیشترین فروش را دارد؟", "پرفروش ترین روز هفته",
            "Best weekday for sales", "Revenue by weekday", "Which weekday has highest revenue?", "Weekday sales analysis",
        ],
        "sql": (
            'SELECT EXTRACT(DOW FROM "order_date")::int AS weekday, SUM("revenue") AS revenue '
            'FROM "orders" GROUP BY 1 ORDER BY revenue DESC'
        ),
        "intent": "ranking", "dimensions": ["weekday"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "monthly_category_trend",
        "description": "Monthly revenue per category",
        "example_questions": [
            "روند ماهانه دسته بندی ها", "فروش ماهانه هر دسته بندی", "عملکرد ماهانه کتگوری ها",
            "Category trend by month", "Monthly category sales", "Monthly category performance",
        ],
        "sql": (
            'SELECT DATE_TRUNC(\'month\', "order_date")::date AS month, "category_level1", SUM("revenue") AS revenue '
            'FROM "orders" GROUP BY 1, "category_level1" ORDER BY month, revenue DESC'
        ),
        "intent": "trend", "dimensions": ["month", "category_level1"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
    {
        "id": "monthly_brand_trend",
        "description": "Monthly revenue per brand",
        "example_questions": [
            "روند ماهانه برندها", "فروش ماهانه برندها", "عملکرد برندها در طول زمان",
            "Brand revenue trend", "Monthly sales by brand", "Brand performance over time",
        ],
        "sql": (
            'SELECT DATE_TRUNC(\'month\', "order_date")::date AS month, "brand_name", SUM("revenue") AS revenue '
            'FROM "orders" GROUP BY 1, "brand_name" ORDER BY month, revenue DESC LIMIT 500'
        ),
        "intent": "trend", "dimensions": ["month", "brand_name"], "metrics": ["revenue"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
    # ------------------------------------------------------------- discounts
    {
        "id": "discount_by_product",
        "description": "Products with the largest total discount",
        "example_questions": [
            "کدام محصولات بیشترین تخفیف را دارند؟", "محصولات با بالاترین تخفیف", "تخفیف هر محصول را نشان بده",
            "بیشترین میزان تخفیف مربوط به چیست؟", "Which products have highest discounts?", "Top discounted products",
            "Products with biggest discounts", "Show discount by product",
        ],
        "sql": 'SELECT "order_items_name", SUM("discount_amount") AS total_discount FROM "orders" GROUP BY "order_items_name" ORDER BY total_discount DESC LIMIT 20',
        "intent": "ranking", "dimensions": ["order_items_name"], "metrics": ["discount"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "top_discount_categories",
        "description": "Categories with the largest total discount",
        "example_questions": [
            "دسته بندی های با بیشترین تخفیف", "کدام کتگوری بیشترین تخفیف را دارد؟", "میزان تخفیف هر دسته بندی",
            "گزارش تخفیف بر اساس کتگوری", "Top discount categories", "Discount amount by category",
            "Which category has the highest total discount?", "Discount analysis by category",
        ],
        "sql": 'SELECT "category_level1", SUM("discount_amount") AS total_discount FROM "orders" GROUP BY "category_level1" ORDER BY total_discount DESC',
        "intent": "ranking", "dimensions": ["category_level1"], "metrics": ["discount"], "filters": [],
        "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "high_discount_low_revenue",
        "description": "Products whose discount is large relative to their revenue",
        "example_questions": [
            "محصولات با تخفیف بالا و درآمد کم", "کدام محصولات تخفیف زیاد ولی فروش کم دارند؟", "محصولات کم سود با تخفیف بالا",
            "نسبت تخفیف به درآمد محصولات", "Products with high discount but low revenue", "Unprofitable discounted products",
            "Products losing money due to discount", "Discount to revenue ratio by product",
        ],
        "sql": (
            'SELECT "order_items_name", SUM("discount_amount") AS total_discount, SUM("revenue") AS revenue, '
            'ROUND(100.0 * SUM("discount_amount") / NULLIF(SUM("revenue"), 0), 2) AS discount_pct '
            'FROM "orders" GROUP BY "order_items_name" HAVING SUM("discount_amount") > 0 '
            'ORDER BY discount_pct DESC LIMIT 20'
        ),
        "intent": "ranking", "dimensions": ["order_items_name"], "metrics": ["discount", "revenue", "share"],
        "filters": ['HAVING SUM("discount_amount") > 0'], "time_filter": None, "supports_top_n": True,
    },
    {
        "id": "discount_vs_no_discount",
        "description": "Revenue from discounted vs non-discounted sales",
        "example_questions": [
            "فروش محصولات با تخفیف نسبت به بدون تخفیف", "مقایسه فروش با تخفیف و بدون تخفیف", "درآمد سفارش های تخفیف دار در مقابل بدون تخفیف",
            "چقدر از فروش با تخفیف بوده؟", "Discounted vs non-discounted sales", "Revenue with discount vs without discount",
            "Compare sales with and without discount", "Share of discounted revenue",
        ],
        "sql": (
            'SELECT CASE WHEN "discount_amount" > 0 THEN \'With Discount\' ELSE \'No Discount\' END AS discount_status, '
            'SUM("revenue") AS revenue FROM "orders" GROUP BY 1 ORDER BY revenue DESC'
        ),
        "intent": "comparison", "dimensions": ["discount_status"], "metrics": ["revenue", "discount", "share"], "filters": [],
        "time_filter": None, "supports_top_n": False,
    },
]

REQUIRED_KEYS = {"id", "description", "example_questions", "sql", "intent", "dimensions", "metrics",
                 "filters", "time_filter", "supports_top_n"}


def validate_templates(templates: List[Dict] | None = None) -> List[str]:
    """Return a list of metadata problems (empty list == OK). Used by build_index / tests."""
    templates = templates if templates is not None else SQL_TEMPLATES
    problems: List[str] = []
    seen_ids: set = set()
    seen_questions: Dict[str, str] = {}
    for t in templates:
        missing = REQUIRED_KEYS - set(t)
        if missing:
            problems.append(f"{t.get('id')}: missing keys {sorted(missing)}")
        if t.get("id") in seen_ids:
            problems.append(f"duplicate template id {t.get('id')}")
        seen_ids.add(t.get("id"))
        for q in t.get("example_questions") or []:
            key = q.strip().lower()
            if key in seen_questions and seen_questions[key] != t["id"]:
                problems.append(f"duplicate example question '{q}' in {t['id']} and {seen_questions[key]}")
            seen_questions[key] = t["id"]
    return problems


def get_all_templates() -> List[Dict]:
    return SQL_TEMPLATES


def get_template(template_id: str) -> Dict | None:
    return next((t for t in SQL_TEMPLATES if t["id"] == template_id), None)
