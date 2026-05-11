# ===================== Imports =====================
import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime

# ===================== ENV =====================
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL is not set in .env file")

print("🔌 Connecting to database...")

# ===================== ENGINE (FIXED - NO DRIVER ISSUES) =====================
# ✅ Use modern psycopg driver (recommended)
# Make sure you installed:
# pip install psycopg[binary]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

# ===================== OUTPUT FILE =====================
output_file = r"E:\cursor projects\Strucured data agent\evaluation_dataset.csv"

# ===================== Queries (40 queries) =====================
queries = [
    # 1-5: Basic Aggregations (Revenue & Orders)
    {"question": "مجموع فروش کل چقدره؟", 
     "sql": "SELECT SUM(revenue) AS total_revenue FROM orders;"},
    
    {"question": "تعداد کل سفارشات چندتا است؟", 
     "sql": "SELECT COUNT(DISTINCT order_id) AS total_orders FROM orders;"},
    
    {"question": "مجموع فروش سوپرمارکت چقدره؟", 
     "sql": "SELECT SUM(revenue) AS total_revenue FROM orders WHERE Category_Level1 = 'سوپرمارکت';"},
    
    {"question": "مجموع فروش آرایشی بهداشتی چقدره؟", 
     "sql": "SELECT SUM(revenue) AS total_revenue FROM orders WHERE Category_Level1 = 'آرایشی بهداشتی';"},
    
    {"question": "میانگین ارزش هر سفارش چقدره؟", 
     "sql": "SELECT ROUND(AVG(revenue), 0) AS avg_order_value FROM orders;"},

    # 6-10: Time-based Analysis
    {"question": "مجموع فروش در ماه جون 2025 چقدر بوده؟", 
     "sql": "SELECT SUM(revenue) AS june_revenue FROM orders WHERE order_date BETWEEN '2025-06-01' AND '2025-06-30';"},
    
    {"question": "مجموع فروش در ماه می 2025", 
     "sql": "SELECT SUM(revenue) AS may_revenue FROM orders WHERE order_date BETWEEN '2025-05-01' AND '2025-05-31';"},
    
    {"question": "فروش روزانه در شهریور 2025", 
     "sql": "SELECT DATE(order_date) AS sale_date, SUM(revenue) AS daily_revenue FROM orders WHERE order_date BETWEEN '2025-09-01' AND '2025-09-30' GROUP BY DATE(order_date) ORDER BY sale_date;"},
    
    {"question": "تعداد سفارشات کامل شده در تهران", 
     "sql": "SELECT COUNT(DISTINCT order_id) AS tehran_orders FROM orders WHERE city = 'تهران' AND status = 'complete';"},
    
    {"question": "فروش ماهانه کل سال 2025", 
     "sql": "SELECT DATE_TRUNC('month', order_date)::date AS month, SUM(revenue) AS monthly_revenue FROM orders GROUP BY DATE_TRUNC('month', order_date) ORDER BY month;"},

    # 11-20: Category & Brand Analysis
    {"question": "تاپ 5 برند از نظر فروش", 
     "sql": "SELECT BrandName, SUM(revenue) AS total_revenue FROM orders GROUP BY BrandName ORDER BY total_revenue DESC LIMIT 5;"},
    
    {"question": "فروش هر دسته اصلی (Category_Level1)", 
     "sql": "SELECT Category_Level1, SUM(revenue) AS revenue FROM orders GROUP BY Category_Level1 ORDER BY revenue DESC;"},
    
    {"question": "فروش برند Liesel چقدر بوده؟", 
     "sql": "SELECT SUM(revenue) AS liesel_revenue FROM orders WHERE BrandName = 'Liesel';"},
    
    {"question": "تاپ 10 محصول پرفروش", 
     "sql": "SELECT order_items_name, SUM(quantity) AS total_qty, SUM(revenue) AS revenue FROM orders GROUP BY order_items_name ORDER BY revenue DESC LIMIT 10;"},
    
    {"question": "درآمد از محصولات سوپرمارکت نسبت به کل فروش", 
     "sql": """SELECT 
                SUM(CASE WHEN Category_Level1 = 'سوپرمارکت' THEN revenue ELSE 0 END) AS supermarket_revenue,
                SUM(revenue) AS total_revenue,
                ROUND(SUM(CASE WHEN Category_Level1 = 'سوپرمارکت' THEN revenue ELSE 0 END) * 100.0 / SUM(revenue), 2) AS supermarket_percentage
               FROM orders;"""},

    # 21-30: Customer & City Analysis
    {"question": "تاپ 5 مشتری از نظر خرید", 
     "sql": "SELECT customer_name, SUM(revenue) AS total_spent FROM orders GROUP BY customer_name ORDER BY total_spent DESC LIMIT 5;"},
    
    {"question": "فروش هر شهر (تاپ 10)", 
     "sql": "SELECT city, SUM(revenue) AS city_revenue FROM orders GROUP BY city ORDER BY city_revenue DESC LIMIT 10;"},
    
    {"question": "میانگین ارزش سفارش در تهران", 
     "sql": "SELECT ROUND(AVG(revenue), 0) AS avg_order_tehran FROM orders WHERE city = 'تهران';"},
    
    {"question": "تعداد مشتریان منحصر به فرد", 
     "sql": "SELECT COUNT(DISTINCT customer_id) AS unique_customers FROM orders;"},
    
    {"question": "فروش به مشتریان زن", 
     "sql": "SELECT SUM(revenue) AS female_revenue FROM orders WHERE Gender LIKE '%زنانه%';"},

    # 31-40: Advanced & Mixed Queries
    {"question": "تاپ 5 شهر از نظر تعداد سفارش", 
     "sql": "SELECT city, COUNT(DISTINCT order_id) AS order_count FROM orders GROUP BY city ORDER BY order_count DESC LIMIT 5;"},
    
    {"question": "میانگین تخفیف اعمال شده", 
     "sql": "SELECT ROUND(AVG(discount_amount), 0) AS avg_discount FROM orders WHERE discount_amount > 0;"},
    
    {"question": "فروش محصولات با تخفیف نسبت به بدون تخفیف", 
     "sql": """SELECT 
                CASE WHEN discount_amount > 0 THEN 'With Discount' ELSE 'No Discount' END AS discount_status,
                SUM(revenue) AS revenue
               FROM orders GROUP BY discount_status;"""},
    
    {"question": "رشد فروش از ماه می به جون", 
     "sql": """WITH monthly AS (
                SELECT 
                  DATE_TRUNC('month', order_date)::date AS month,
                  SUM(revenue) AS revenue
                FROM orders 
                WHERE order_date BETWEEN '2025-05-01' AND '2025-06-30'
                GROUP BY DATE_TRUNC('month', order_date)
               )
               SELECT 
                 (MAX(CASE WHEN month = '2025-06-01' THEN revenue END) - 
                  MAX(CASE WHEN month = '2025-05-01' THEN revenue END)) * 100.0 /
                  MAX(CASE WHEN month = '2025-05-01' THEN revenue END) AS growth_percent
               FROM monthly;"""},
    
    {"question": "پرفروش‌ترین محصول در سوپرمارکت", 
     "sql": "SELECT order_items_name, SUM(revenue) AS revenue FROM orders WHERE Category_Level1 = 'سوپرمارکت' GROUP BY order_items_name ORDER BY revenue DESC LIMIT 3;"},
]

# ===================== Run Queries =====================
# ===================== RUN =====================
results = []
print("🚀 Running queries...\n")

for i, item in enumerate(queries, 1):
    try:
        df = pd.read_sql(text(item["sql"]), engine)

        if df.empty:
            result = "No data"
            result_type = "empty"
        elif df.shape == (1, 1):
            result = str(df.iloc[0, 0])
            result_type = "scalar"
        else:
            result = df.to_string(index=False)
            result_type = "table"

        results.append({
            "id": i,
            "question": item["question"],
            "sql": item["sql"].strip(),
            "result": result,
            "result_type": result_type,
            "row_count": len(df),
            "status": "success",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        print(f"✅ {i:2d} → Success")

    except Exception as e:
        print(f"❌ {i:2d} → {str(e)[:80]}")

        results.append({
            "id": i,
            "question": item["question"],
            "sql": item["sql"].strip(),
            "result": f"ERROR: {str(e)}",
            "result_type": "error",
            "row_count": 0,
            "status": "error",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

# ===================== SAVE =====================
df_eval = pd.DataFrame(results)
df_eval.to_csv(output_file, index=False, encoding="utf-8-sig")

print("\n🎉 DONE!")
print(f"📁 Saved to: {output_file}")
print(f"✅ Success: {len(df_eval[df_eval['status']=='success'])}/{len(df_eval)}")