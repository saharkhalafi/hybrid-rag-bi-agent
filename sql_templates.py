# sql_templates.py
import json
from typing import List, Dict

SQL_TEMPLATES = [
    {
        "id": "total_by_category",
        "description": "Total quantity and revenue by category",
        "sql_summary": "Aggregates total ordered quantity and total revenue for each product category and ranks categories by highest revenue.",
        "example_questions": [
            "What are total sales by category?",
            "Show revenue by category",
            "Total quantity sold per category",
            "Which category has highest revenue?",
            "Sales performance by category",
            "مجموع فروش هر دسته بندی چقدر است؟",
            "درآمد هر کتگوری را نشان بده",
            "کدام دسته بندی بیشترین فروش را دارد؟",
            "تعداد فروش هر دسته بندی چقدر بوده؟",
            "عملکرد فروش دسته بندی ها را نمایش بده"
        ],
        "sql": """
        SELECT
    "category_level1",
    SUM("ordered_qty") AS total_qty,
    SUM("revenue") AS total_revenue
FROM "orders"
GROUP BY "category_level1"
ORDER BY total_revenue DESC
LIMIT 20     
        """
    },

    {
        "id": "top_selling_products",
        "description": "Top best selling products",
        "sql_summary": "Finds the top selling products based on total quantity sold and returns the highest performing items.",
        "example_questions": [
            "Show top 10 products",
            "Best selling products",
            "Top products by quantity sold",
            "Most popular products",
            "Which products sold the most?",
            "پرفروش ترین محصولات را نشان بده",
            "۱۰ محصول برتر فروش",
            "کدام محصولات بیشترین فروش را داشتند؟",
            "محصولات محبوب مشتریان",
            "بیشترین تعداد فروش مربوط به کدام محصول است؟"
        ],
        "sql": """
        SELECT
    "order_items_name",
    SUM("ordered_qty") AS total_sold
FROM "orders"
GROUP BY "order_items_name"
ORDER BY total_sold DESC
LIMIT 10

        """
    },

    {
        "id": "monthly_sales_trend",
        "description": "Monthly revenue trend",
        "sql_summary": "Calculates total monthly revenue over time to analyze monthly sales and business growth trends.",
        "example_questions": [
            "Monthly sales trend in 2025",
            "Revenue trend by month",
            "Monthly revenue report",
            "Sales growth over months",
            "Show monthly sales chart",
            "روند فروش ماهانه را نشان بده",
            "درآمد ماهانه در سال ۲۰۲۵",
            "گزارش فروش ماه به ماه",
            "روند رشد فروش ماهانه",
            "نمودار فروش ماهانه را نمایش بده"
        ],
        "sql": """
       SELECT
    DATE_TRUNC('month', "order_date") AS month,
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY month
ORDER BY month
LIMIT 30 
        """
    },

    {
        "id": "daily_sales_trend",
        "description": "Daily sales trend",
        "sql_summary": "Shows daily revenue trends by aggregating sales revenue for each day.",
        "example_questions": [
            "Daily sales trend",
            "Revenue by day",
            "Daily revenue report",
            "Show daily sales",
            "Sales trend day by day",
            "روند فروش روزانه",
            "درآمد روزانه را نمایش بده",
            "گزارش فروش روزانه",
            "فروش هر روز چقدر بوده؟",
            "روند فروش به صورت روزانه"
        ],
        "sql": """
        SELECT
    DATE_TRUNC('day', "order_date") AS day,
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY day
ORDER BY day
LIMIT 30 

        """
    },

    {
        "id": "yearly_sales",
        "description": "Yearly revenue summary",
        "sql_summary": "Summarizes annual revenue performance by grouping sales data by year.",
        "example_questions": [
            "Revenue by year",
            "Yearly sales report",
            "Annual revenue summary",
            "Sales trend by year",
            "Compare yearly revenue",
            "فروش سالانه را نشان بده",
            "درآمد هر سال چقدر بوده؟",
            "گزارش فروش سالانه",
            "مقایسه درآمد سال ها",
            "روند فروش سالانه"
        ],
        "sql": """
        SELECT
    DATE_TRUNC('year', "order_date") AS year,
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY year
ORDER BY year
LIMIT 100
        
        """
    },

    {
        "id": "top_brands",
        "description": "Top brands by revenue",
        "sql_summary": "Ranks brands based on total generated revenue and identifies the highest performing brands.",
        "example_questions": [
            "Top brands",
            "Best brands by sales",
            "Brands with highest revenue",
            "Top performing brands",
            "Most profitable brands",
            "برندهای برتر",
            "کدام برند بیشترین فروش را دارد؟",
            "درآمد برندها را نشان بده",
            "برندهای پرفروش",
            "بهترین برندها از نظر درآمد"
        ],
        "sql": """..."""
    },

    {
        "id": "top_categories_revenue",
        "description": "Top categories by revenue",
        "sql_summary": "Returns product categories with the highest total revenue contribution.",
        "example_questions": [
            "Highest revenue categories",
            "Top categories by sales",
            "Best categories",
            "Most profitable categories",
            "Revenue ranking of categories",
            "دسته بندی های با بیشترین درآمد",
            "پرفروش ترین دسته بندی ها",
            "بهترین کتگوری ها از نظر فروش",
            "رتبه بندی دسته بندی ها بر اساس درآمد",
            "کدام کتگوری بیشترین سود را دارد؟"
        ],
        "sql": """
        SELECT
    "brand_name",
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY "brand_name"
ORDER BY revenue DESC
LIMIT 20
        
        """
    },

    {
        "id": "top_cities",
        "description": "Top cities by revenue",
        "sql_summary": "Identifies cities generating the highest revenue from customer orders.",
        "example_questions": [
            "Top cities by sales",
            "Revenue by city",
            "Which cities generate most revenue?",
            "Best performing cities",
            "Top cities for orders",
            "شهرهای برتر از نظر فروش",
            "درآمد هر شهر را نشان بده",
            "کدام شهر بیشترین فروش را دارد؟",
            "بهترین شهرها از نظر سفارش",
            "فروش بر اساس شهر"
        ],
        "sql": """
        SELECT
    "category_level1",
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY "category_level1"
ORDER BY revenue DESC
LIMIT 10
        
        """
    },

    {
        "id": "discount_analysis",
        "description": "Products with highest discount",
        "sql_summary": "Analyzes products receiving the largest total discount amounts across all orders.",
        "example_questions": [
            "Which products have highest discounts?",
            "Top discounted products",
            "Products with biggest discounts",
            "Discount analysis",
            "Show discount by product",
            "کدام محصولات بیشترین تخفیف را دارند؟",
            "محصولات با بالاترین تخفیف",
            "تحلیل تخفیف محصولات",
            "تخفیف هر محصول را نشان بده",
            "بیشترین میزان تخفیف مربوط به چیست؟"
        ],
        "sql": """
        SELECT
    "city_name",
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY "city_name"
ORDER BY revenue DESC
LIMIT 10 
        
        """
    },

    {
        "id": "high_discount_low_revenue",
        "description": "High discount but low revenue products",
        "sql_summary": "Finds products with very high discount amounts but relatively low revenue generation.",
        "example_questions": [
            "Products with high discount but low revenue",
            "Low revenue products with large discounts",
            "Unprofitable discounted products",
            "Products losing money due to discount",
            "High discount low sales items",
            "محصولات با تخفیف بالا و درآمد کم",
            "کدام محصولات تخفیف زیاد ولی فروش کم دارند؟",
            "محصولات کم سود با تخفیف بالا",
            "تحلیل تخفیف و درآمد محصولات",
            "آیتم های با تخفیف زیاد و فروش پایین"
        ],
        "sql": """
        SELECT
    "order_items_name",
    SUM("discount_amount") AS total_discount
FROM "orders"
GROUP BY "order_items_name"
ORDER BY total_discount DESC
LIMIT 20     
        """
    },

    {
        "id": "revenue_by_gender",
        "description": "Revenue grouped by gender",
        "sql_summary": "Groups and compares total revenue generated by different customer genders.",
        "example_questions": [
            "Revenue by gender",
            "Sales by gender",
            "Compare male and female revenue",
            "Customer gender analysis",
            "Which gender buys more?",
            "فروش بر اساس جنسیت",
            "درآمد مشتریان زن و مرد",
            "مقایسه فروش بین جنسیت ها",
            "کدام جنسیت خرید بیشتری دارد؟",
            "تحلیل جنسیت مشتریان"
        ],
        "sql": """
SELECT
    "gender",
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY "gender"
ORDER BY revenue DESC
LIMIT 10
        
        """
    },

    {
        "id": "average_order_value",
        "description": "Average order value",
        "sql_summary": "Calculates the average revenue value generated per order across the dataset.",
        "example_questions": [
            "Average order revenue",
            "Average basket size",
            "Average purchase amount",
            "Mean order value",
            "What is the average revenue per order?",
            "میانگین ارزش سفارش چقدر است؟",
            "میانگین مبلغ خرید مشتریان",
            "میانگین درآمد هر سفارش",
            "متوسط ارزش سبد خرید",
            "هر سفارش به طور میانگین چقدر درآمد دارد؟"
        ],
        "sql": """SELECT
    AVG("revenue") AS avg_order_value
FROM "orders"
LIMIT 1
"""
    },

    {
        "id": "order_count",
        "description": "Total orders count",
        "sql_summary": "Counts the total number of orders available in the orders table.",
        "example_questions": [
            "How many orders exist?",
            "Total order count",
            "Number of all orders",
            "Count all orders",
            "How many purchases were made?",
            "تعداد کل سفارش ها چقدر است؟",
            "چند سفارش ثبت شده؟",
            "تعداد کل خریدها",
            "آمار تعداد سفارش ها",
            "چند خرید انجام شده است؟"
        ],
        "sql": """
        SELECT
    COUNT(*) AS total_orders
FROM "orders"
LIMIT 1
        """
    },

    {
        "id": "revenue_by_brand",
        "description": "Revenue by brand",
        "sql_summary": "Aggregates and compares total revenue generated by each brand.",
        "example_questions": [
            "Revenue by brand",
            "Brand sales report",
            "Compare brands by revenue",
            "Brand performance analysis",
            "Sales per brand",
            "درآمد برندها را نشان بده",
            "فروش هر برند",
            "مقایسه برندها بر اساس درآمد",
            "تحلیل عملکرد برندها",
            "کدام برند بیشترین فروش را دارد؟"
        ],
        "sql": """SELECT
    "brand_name",
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY "brand_name"
ORDER BY revenue DESC
LIMIT 30"""
    },

    {
        "id": "revenue_by_city",
        "description": "Revenue by city",
        "sql_summary": "Shows total revenue generated from each city and ranks cities by revenue.",
        "example_questions": [
            "Revenue by city",
            "Sales by city",
            "City revenue analysis",
            "Compare cities by revenue",
            "Top revenue cities",
            "درآمد شهرها را نشان بده",
            "فروش هر شهر",
            "تحلیل فروش بر اساس شهر",
            "مقایسه درآمد شهرها",
            "کدام شهر بیشترین درآمد را دارد؟"
        ],
        "sql": """SELECT
    "city_name",
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY "city_name"
ORDER BY revenue DESC
LIMIT 50"""
    },

    {
        "id": "top_customers",
        "description": "Top customers by revenue",
        "sql_summary": "Identifies customers contributing the highest total revenue through purchases.",
        "example_questions": [
            "Top customers",
            "Best customers by revenue",
            "Highest spending customers",
            "VIP customers",
            "Customers generating most revenue",
            "بهترین مشتریان",
            "مشتریانی با بیشترین خرید",
            "مشتریان VIP",
            "کدام مشتری بیشترین درآمد ایجاد کرده؟",
            "مشتریان برتر از نظر فروش"
        ],
        "sql": """SELECT
    "customer_name",
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY "customer_name"
ORDER BY revenue DESC
LIMIT 20"""
    },

    {
        "id": "monthly_category_trend",
        "description": "Monthly category trend",
        "sql_summary": "Tracks monthly revenue trends for each product category over time.",
        "example_questions": [
            "Category trend by month",
            "Monthly category sales",
            "Revenue trend per category",
            "Category growth monthly",
            "Monthly category performance",
            "روند ماهانه دسته بندی ها",
            "فروش ماهانه هر دسته بندی",
            "روند درآمد کتگوری ها",
            "رشد ماهانه دسته بندی ها",
            "عملکرد ماهانه کتگوری ها"
        ],
        "sql": """
SELECT
    DATE_TRUNC('month', "order_date") AS month,
    "category_level1",
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY month, "category_level1"
ORDER BY month
LIMIT 30
"""
    },

    {
        "id": "monthly_brand_trend",
        "description": "Monthly brand trend",
        "sql_summary": "Analyzes monthly revenue performance and trends for each brand.",
        "example_questions": [
            "Brand revenue trend",
            "Monthly sales by brand",
            "Brand performance over time",
            "Monthly brand growth",
            "Brand trend analysis",
            "روند ماهانه برندها",
            "فروش ماهانه برندها",
            "تحلیل روند برندها",
            "رشد ماهانه برندها",
            "عملکرد برندها در طول زمان"
        ],
        "sql":"""SELECT
    DATE_TRUNC('month', "order_date") AS month,
    "brand_name",
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY month, "brand_name"
ORDER BY month
LIMIT 30"""
    },

    {
        "id": "low_selling_products",
        "description": "Lowest selling products",
        "sql_summary": "Finds products with the lowest sales quantity across all orders.",
        "example_questions": [
            "Worst selling products",
            "Low demand products",
            "Products with lowest sales",
            "Slow moving products",
            "Least popular products",
            "کم فروش ترین محصولات",
            "محصولات با فروش پایین",
            "محصولات کم تقاضا",
            "بدترین محصولات از نظر فروش",
            "آیتم های با فروش کم"
        ],
        "sql": """SELECT
    "order_items_name",
    SUM("ordered_qty") AS qty
FROM "orders"
GROUP BY "order_items_name"
ORDER BY qty ASC
LIMIT 20"""
    },

    {
        "id": "category_share",
        "description": "Revenue contribution by category",
        "sql_summary": "Calculates each category’s share and contribution to total revenue.",
        "example_questions": [
            "Category revenue share",
            "Revenue contribution per category",
            "Category market share",
            "Share of each category in total revenue",
            "Category contribution analysis",
            "سهم هر دسته بندی از درآمد",
            "درصد فروش هر کتگوری",
            "تحلیل سهم دسته بندی ها",
            "سهم درآمدی هر دسته بندی",
            "هر کتگوری چه سهمی از فروش دارد؟"
        ],
        "sql": """SELECT
    "category_level1",
    SUM("revenue") AS revenue,
    SUM("revenue") / SUM(SUM("revenue")) OVER () AS revenue_share
FROM "orders"
GROUP BY "category_level1"
ORDER BY revenue DESC
LIMIT 20"""
    },

    {
        "id": "pareto_products",
        "description": "Products contributing to 80 percent revenue",
        "sql_summary": "Performs Pareto analysis to identify products responsible for approximately 80% of total revenue.",
        "example_questions": [
            "Products contributing to 80% revenue",
            "Pareto analysis of products",
            "Top products generating most revenue",
            "Important revenue driving products",
            "80/20 sales analysis",
            "محصولات موثر در ۸۰ درصد درآمد",
            "تحلیل پارتو محصولات",
            "کدام محصولات بیشترین درآمد را ایجاد می کنند؟",
            "تحلیل قانون ۸۰/۲۰ فروش",
            "محصولات کلیدی درآمدزا"
        ],
        "sql": """WITH product_revenue AS (
    SELECT
        "order_items_name",
        SUM("revenue") AS revenue
    FROM "orders"
    GROUP BY "order_items_name"
),
ranked AS (
    SELECT
        *,
        SUM(revenue) OVER (ORDER BY revenue DESC) AS cumulative_revenue,
        SUM(revenue) OVER () AS total_revenue
    FROM product_revenue
)
SELECT
    "order_items_name",
    revenue
FROM ranked
WHERE cumulative_revenue <= total_revenue * 0.8
ORDER BY revenue DESC
LIMIT 100"""
    },
{
    "id": "top_discount_categories",
    "description": "Categories with highest discounts",
    "sql_summary": "Shows categories with the largest total discount amounts applied to orders.",
    "example_questions": [
        "Top discount categories",
        "Categories with biggest discounts",
        "Which categories received highest discounts?",
        "Discount amount by category",
        "Most discounted categories",
        "Show categories with maximum discounts",
        "Discount analysis by category",
        "Which category has the highest total discount?",
        "دسته بندی های با بیشترین تخفیف",
        "کدام کتگوری بیشترین تخفیف را دارد؟",
        "میزان تخفیف هر دسته بندی",
        "تحلیل تخفیف دسته بندی ها",
        "بیشترین تخفیف مربوط به کدام دسته بندی است؟",
        "دسته بندی های دارای بیشترین میزان تخفیف",
        "گزارش تخفیف بر اساس کتگوری",
        "تخفیف کل هر دسته بندی را نشان بده"
    ],
    "sql": """
SELECT
    "category_level1",
    SUM("discount_amount") AS total_discount
FROM "orders"
GROUP BY "category_level1"
ORDER BY total_discount DESC
LIMIT 20
"""
},

{
    "id": "high_revenue_low_quantity",
    "description": "High revenue but low quantity categories",
    "sql_summary": "Finds categories generating high revenue despite low sales quantity, indicating premium or expensive products.",
    "example_questions": [
        "High revenue low quantity categories",
        "Categories with high revenue but low sales volume",
        "Which categories generate high revenue with low quantity?",
        "Low quantity high profit categories",
        "Premium categories with low order quantity",
        "High value low volume categories",
        "Revenue vs quantity by category",
        "Most profitable low quantity categories",
        "دسته بندی های با درآمد بالا و تعداد فروش کم",
        "کدام کتگوری درآمد بالا ولی فروش کم دارد؟",
        "دسته بندی های کم فروش اما پردرآمد",
        "تحلیل درآمد و تعداد فروش دسته بندی ها",
        "محصولات پریمیوم با تعداد فروش کم",
        "کتگوری های با سود بالا و حجم فروش پایین",
        "مقایسه درآمد و تعداد فروش دسته بندی ها",
        "دسته بندی های ارزشمند با فروش کم"
    ],
    "sql": """
SELECT
    "category_level1",
    SUM("revenue") AS revenue,
    SUM("ordered_qty") AS qty
FROM "orders"
GROUP BY "category_level1"
ORDER BY revenue DESC, qty ASC
LIMIT 20
"""
},

{
    "id": "customer_frequency",
    "description": "Customers with highest order frequency",
    "sql_summary": "Identifies customers who place orders most frequently based on order count.",
    "example_questions": [
        "Most frequent customers",
        "Top repeat customers",
        "Customers with highest number of orders",
        "Who orders the most?",
        "Most loyal customers",
        "Customer order frequency",
        "Top active customers",
        "Customers with repeated purchases",
        "مشتریان با بیشترین تعداد سفارش",
        "وفادارترین مشتریان",
        "کدام مشتری بیشتر سفارش داده است؟",
        "مشتریان پرتکرار",
        "بیشترین تعداد خرید مربوط به چه کسی است؟",
        "مشتریان فعال فروشگاه",
        "تحلیل تعداد سفارش مشتریان",
        "مشتریانی با خرید مکرر"
    ],
    "sql": """
SELECT
    "customer_name",
    COUNT(*) AS order_count
FROM "orders"
GROUP BY "customer_name"
ORDER BY order_count DESC
LIMIT 20
"""
},

{
    "id": "average_discount",
    "description": "Average discount amount",
    "sql_summary": "Calculates the average discount amount applied across all orders.",
    "example_questions": [
        "Average discount",
        "Mean discount amount",
        "Average discount per order",
        "What is the average discount value?",
        "Discount average analysis",
        "Typical discount amount",
        "Overall average discounts",
        "Average promotional discount",
        "میانگین تخفیف چقدر است؟",
        "متوسط میزان تخفیف",
        "میانگین تخفیف هر سفارش",
        "تحلیل میانگین تخفیف",
        "مقدار متوسط تخفیف ها",
        "به طور میانگین چقدر تخفیف داده شده؟",
        "گزارش میانگین تخفیف",
        "متوسط تخفیف اعمال شده"
    ],
    "sql": """
SELECT
    AVG("discount_amount") AS avg_discount
FROM "orders"
LIMIT 1
"""
},

{
    "id": "revenue_growth_monthly",
    "description": "Month over month revenue",
    "sql_summary": "Analyzes month-over-month revenue growth trends over time.",
    "example_questions": [
        "Monthly revenue growth",
        "Month over month sales growth",
        "Revenue trend by month",
        "Monthly growth analysis",
        "How is revenue growing monthly?",
        "Monthly sales comparison",
        "Revenue increase month by month",
        "Monthly business growth trend",
        "رشد ماهانه درآمد",
        "روند رشد فروش ماهانه",
        "مقایسه فروش ماه به ماه",
        "درآمد هر ماه چقدر رشد کرده؟",
        "تحلیل رشد ماهانه فروش",
        "روند درآمد ماهانه",
        "افزایش فروش در هر ماه",
        "گزارش رشد ماه به ماه"
    ],
    "sql": """
SELECT
    DATE_TRUNC('month', "order_date") AS month,
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY month
ORDER BY month
LIMIT 100
"""
},

{
    "id": "top_products_by_city",
    "description": "Top products in each city",
    "sql_summary": "Finds the most sold products within each city based on ordered quantity.",
    "example_questions": [
        "Best selling products by city",
        "Top products in each city",
        "Most popular products per city",
        "City wise best sellers",
        "Top selling items across cities",
        "Which products sell best in each city?",
        "Product popularity by city",
        "Top city product analysis",
        "پرفروش ترین محصولات هر شهر",
        "محبوب ترین محصولات در هر شهر",
        "کدام محصولات در هر شهر بهتر فروش دارند؟",
        "تحلیل فروش محصولات بر اساس شهر",
        "بهترین محصولات هر شهر",
        "پرفروش ترین کالاها در شهرها",
        "محصولات محبوب هر منطقه",
        "فروش محصولات به تفکیک شهر"
    ],
    "sql": """
SELECT
    "city_name",
    "order_items_name",
    SUM("ordered_qty") AS qty
FROM "orders"
GROUP BY "city_name", "order_items_name"
ORDER BY qty DESC
LIMIT 100
"""
},

{
    "id": "inactive_products",
    "description": "Products with very low sales",
    "sql_summary": "Identifies products with extremely low sales volume and minimal customer demand.",
    "example_questions": [
        "Inactive products",
        "Products with lowest sales",
        "Slow moving products",
        "Unsold products",
        "Products with poor performance",
        "Low demand products",
        "Which products rarely sell?",
        "Products with minimal orders",
        "محصولات کم فروش",
        "محصولات بدون فروش مناسب",
        "کدام محصولات فروش کمی دارند؟",
        "محصولات با عملکرد ضعیف",
        "کالاهای کم تقاضا",
        "محصولات غیرفعال",
        "آیتم هایی با سفارش کم",
        "محصولات با حداقل فروش"
    ],
    "sql": """
SELECT
    "order_items_name",
    SUM("ordered_qty") AS qty
FROM "orders"
GROUP BY "order_items_name"
HAVING SUM("ordered_qty") < 5
ORDER BY qty ASC
LIMIT 100
"""
},

{
    "id": "revenue_by_weekday",
    "description": "Revenue by weekday",
    "sql_summary": "Compares total revenue generated on different weekdays to identify the strongest sales days.",
    "example_questions": [
        "Best weekday for sales",
        "Revenue by weekday",
        "Sales performance by day of week",
        "Which weekday has highest revenue?",
        "Daily revenue comparison",
        "Weekday sales analysis",
        "Best day for business",
        "Revenue trends during the week",
        "بهترین روز هفته برای فروش",
        "درآمد بر اساس روز هفته",
        "کدام روز هفته بیشترین فروش را دارد؟",
        "تحلیل فروش روزهای هفته",
        "مقایسه درآمد در روزهای هفته",
        "عملکرد فروش در طول هفته",
        "پرفروش ترین روز هفته",
        "روند درآمد در روزهای مختلف هفته"
    ],
    "sql": """
SELECT
    EXTRACT(DOW FROM "order_date") AS weekday,
    SUM("revenue") AS revenue
FROM "orders"
GROUP BY weekday
ORDER BY revenue DESC
LIMIT 10
"""
}    
]

def get_all_templates() -> List[Dict]:
    return SQL_TEMPLATES


def get_template_descriptions() -> str:
    """Return formatted string for embedding or prompting"""
    lines = []
    for t in SQL_TEMPLATES:
        lines.append(f"Template ID: {t['id']}")
        lines.append(f"Description: {t['description']}")
        lines.append(f"Example: {t['example_question']}")
        lines.append("---")
    return "\n".join(lines)