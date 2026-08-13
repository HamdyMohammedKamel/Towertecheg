import sqlite3
from datetime import datetime
import io
import pandas as pd
import streamlit as st

# ---------------------------------------------------------
# SETUP & CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="نظام إدارة المخازن المتكامل", page_icon="📦", layout="wide"
)

DB_NAME = "inventory_system.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # جدول المستخدمين
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        full_name TEXT
    )
    """)

    # جدول المخازن
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        type TEXT NOT NULL,
        location TEXT
    )
    """)

    # جدول الأصناف (المنتجات)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        min_limit INTEGER DEFAULT 5
    )
    """)

    # جدول رصيد المخزون (منتج + مخزن)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        product_code TEXT,
        warehouse_id INTEGER,
        quantity INTEGER DEFAULT 0,
        PRIMARY KEY (product_code, warehouse_id),
        FOREIGN KEY (product_code) REFERENCES products (code),
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
    )
    """)

    # جدول سجل الحركات
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        product_code TEXT NOT NULL,
        warehouse_id INTEGER NOT NULL,
        trans_type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        user TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY (product_code) REFERENCES products (code),
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
    )
    """)

    # إنشاء حساب المدير الافتراضي وإضافة المخزن الرئيسي إذا لم يكن موجوداً
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users VALUES ('admin', 'admin123', 'Admin', 'مدير النظام')"
        )

    cursor.execute("SELECT * FROM warehouses WHERE name = 'المخزن الرئيسي'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO warehouses (name, type, location) VALUES ('المخزن الرئيسي', 'رئيسي', 'المقر الرئيسي')"
        )

    conn.commit()
    conn.close()


init_db()

# ---------------------------------------------------------
# AUTHENTICATION SESSION
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["role"] = ""
    st.session_state["full_name"] = ""


def login_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, password),
    )
    user = cursor.fetchone()
    conn.close()
    if user:
        st.session_state["logged_in"] = True
        st.session_state["username"] = user["username"]
        st.session_state["role"] = user["role"]
        st.session_state["full_name"] = user["full_name"]
        return True
    return False


def logout_user():
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["role"] = ""
    st.session_state["full_name"] = ""
    st.rerun()


# ---------------------------------------------------------
# LOGIN SCREEN
# ---------------------------------------------------------
if not st.session_state["logged_in"]:
    st.markdown(
        "<h2 style='text-align: center;'>🔒 تسجيل الدخول إلى نظام المخازن</h2>",
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user_input = st.text_input("اسم المستخدم")
            pass_input = st.text_input("كلمة المرور", type="password")
            submit = st.form_submit_button("دخول", use_container_width=True)

            if submit:
                if login_user(user_input, pass_input):
                    st.success("تم تسجيل الدخول بنجاح!")
                    st.rerun()
                else:
                    st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
        st.info("💡 حساب المدير الافتراضي: admin | كلمة المرور: admin123")
    st.stop()

# ---------------------------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------------------------
st.sidebar.title(f"مرحباً، {st.session_state['full_name']}")
st.sidebar.caption(f"الصلاحية: {st.session_state['role']}")

menu_options = [
    "لوحة التحكم والمخزون",
    "تسجيل حركة (صرف/توريد/مرتجع)",
    "إدارة الأصناف",
    "إدارة المخازن",
    "التقارير والتصدير",
]

if st.session_state["role"] == "Admin":
    menu_options.append("إدارة المستخدمين")

choice = st.sidebar.radio("القائمة الرئيسية", menu_options)

if st.sidebar.button("تسجيل الخروج", use_container_width=True):
    logout_user()

# ---------------------------------------------------------
# 1. DASHBOARD & INVENTORY VIEW
# ---------------------------------------------------------
if choice == "لوحة التحكم والمخزون":
    st.header("📊 حالة المخزون التفاعلية والتنبيهات")

    conn = get_connection()
    df_inv = pd.read_sql_query(
        """
        SELECT 
            p.code AS 'كود الصنف',
            p.name AS 'اسم الصنف',
            p.category AS 'التصنيف',
            w.name AS 'المخزن',
            COALESCE(i.quantity, 0) AS 'الكمية الحالية',
            p.min_limit AS 'حد الأمان'
        FROM products p
        CROSS JOIN warehouses w
        LEFT JOIN inventory i ON p.code = i.product_code AND w.id = i.warehouse_id
    """,
        conn,
    )
    conn.close()

    # التنبيهات (حد الأمان)
    alerts = df_inv[df_inv["الكمية الحالية"] <= df_inv["حد الأمان"]]

    if not alerts.empty:
        st.warning(
            f"⚠️ يوجد عدد ({len(alerts)}) أصناف بلغت أو أقل من حد الأمان المطلوب!"
        )
        st.dataframe(alerts, use_container_width=True)

    st.subheader("📋 رصيد كافة الأصناف بالمخازن")
    st.dataframe(df_inv, use_container_width=True)

# ---------------------------------------------------------
# 2. TRANSACTIONS SCREEN
# ---------------------------------------------------------
elif choice == "تسجيل حركة (صرف/توريد/مرتجع)":
    st.header("📝 تسجيل حركة مخزنية")

    conn = get_connection()
    products = pd.read_sql_query("SELECT code, name FROM products", conn)
    warehouses = pd.read_sql_query("SELECT id, name FROM warehouses", conn)

    if products.empty or warehouses.empty:
        st.error(
            "يرجى التأكد من إضافة أصناف ومخازن أولاً قبل تسجيل أي حركة!"
        )
    else:
        prod_dict = {
            f"{row['code']} - {row['name']}": row["code"]
            for _, row in products.iterrows()
        }
        wh_dict = {
            row["name"]: row["id"] for _, row in warehouses.iterrows()
        }

        with st.form("trans_form"):
            col1, col2 = st.columns(2)
            with col1:
                prod_selected = st.selectbox("اختر الصنف", list(prod_dict.keys()))
                wh_selected = st.selectbox("اختر المخزن", list(wh_dict.keys()))
                trans_type = st.selectbox(
                    "نوع الحركة", ["توريد (إضافة)", "صرف (خصم)", "مرتجع"]
                )
            with col2:
                quantity = st.number_input(
                    "الكمية", min_value=1, step=1, value=1
                )
                notes = st.text_area("ملاحظات / رقم الإذن / المورد أو العميل")

            submit = st.form_submit_button(
                "تسجيل الحركة", use_container_width=True
            )

            if submit:
                p_code = prod_dict[prod_selected]
                w_id = wh_dict[wh_selected]

                cursor = conn.cursor()

                # جلب الرصيد الحالي
                cursor.execute(
                    "SELECT quantity FROM inventory WHERE product_code = ? AND warehouse_id = ?",
                    (p_code, w_id),
                )
                res = cursor.fetchone()
                current_qty = res["quantity"] if res else 0

                # حساب الكمية الجديدة
                if trans_type in ["توريد (إضافة)", "مرتجع"]:
                    new_qty = current_qty + quantity
                else:  # صرف
                    if current_qty < quantity:
                        st.error(
                            f"❌ الرصيد غير كافٍ! الرصيد الحالي بالمخزن هو: {current_qty}"
                        )
                        st.stop()
                    new_qty = current_qty - quantity

                # تحديث أو إضافة الرصيد
                cursor.execute(
                    """
                    INSERT INTO inventory (product_code, warehouse_id, quantity) 
                    VALUES (?, ?, ?) 
                    ON CONFLICT(product_code, warehouse_id) 
                    DO UPDATE SET quantity = ?
                """,
                    (p_code, w_id, new_qty, new_qty),
                )

                # حفظ الحركة في سجل الحركات
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    """
                    INSERT INTO transactions (date, product_code, warehouse_id, trans_type, quantity, user, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        now_str,
                        p_code,
                        w_id,
                        trans_type,
                        quantity,
                        st.session_state["username"],
                        notes,
                    ),
                )

                conn.commit()
                st.success("✅ تم تسجيل الحركة وتحديث الرصيد بنجاح!")
    conn.close()

# ---------------------------------------------------------
# 3. MANAGE PRODUCTS
# ---------------------------------------------------------
elif choice == "إدارة الأصناف":
    st.header("📦 إضافة وتعديل الأصناف")

    with st.form("add_product"):
        col1, col2 = st.columns(2)
        with col1:
            p_code = st.text_input("كود الصنف (الباركود / الرقم التعريفي)")
            p_name = st.text_input("اسم الصنف")
        with col2:
            p_cat = st.text_input("التصنيف (مثال: قطع غيار / مواد خام)")
            p_min = st.number_input(
                "حد الأمان (التنبيه عند النقص)", min_value=0, value=5
            )

        submit = st.form_submit_button("حفظ الصنف جديد")

        if submit:
            if not p_code or not p_name:
                st.error("يرجى إدخال الكود واسم الصنف!")
            else:
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO products VALUES (?, ?, ?, ?)",
                        (p_code, p_name, p_cat, p_min),
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"تمت إضافة الصنف {p_name} بنجاح!")
                except sqlite3.IntegrityError:
                    st.error("كود الصنف موجود بالفعل!")

    st.subheader("📋 قائمة الأصناف المسجلة")
    conn = get_connection()
    df_p = pd.read_sql_query(
        "SELECT code AS 'الكود', name AS 'الاسم', category AS 'التصنيف', min_limit AS 'حد الأمان' FROM products",
        conn,
    )
    conn.close()
    st.dataframe(df_p, use_container_width=True)

# ---------------------------------------------------------
# 4. MANAGE WAREHOUSES
# ---------------------------------------------------------
elif choice == "إدارة المخازن":
    st.header("🏢 إضافة المخازن (الرئيسية والفرعية)")

    with st.form("add_wh"):
        col1, col2 = st.columns(2)
        with col1:
            w_name = st.text_input("اسم المخزن")
            w_type = st.selectbox("نوع المخزن", ["فرعي", "رئيسي"])
        with col2:
            w_loc = st.text_input("الموقع / العنوان")

        submit = st.form_submit_button("إضافة مخزن")

        if submit:
            if not w_name:
                st.error("يرجى إدخال اسم المخزن!")
            else:
                try:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO warehouses (name, type, location) VALUES (?, ?, ?)",
                        (w_name, w_type, w_loc),
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"تمت إضافة {w_name} بنجاح!")
                except sqlite3.IntegrityError:
                    st.error("اسم المخزن موجود بالفعل!")

    st.subheader("🏢 المخازن المتاحة")
    conn = get_connection()
    df_w = pd.read_sql_query(
        "SELECT id AS 'المعرف', name AS 'اسم المخزن', type AS 'النوع', location AS 'الموقع' FROM warehouses",
        conn,
    )
    conn.close()
    st.dataframe(df_w, use_container_width=True)

# ---------------------------------------------------------
# 5. REPORTS & EXCEL EXPORT
# ---------------------------------------------------------
elif choice == "التقارير والتصدير":
    st.header("📈 تقارير الحركة والمخزون")

    tab1, tab2 = st.tabs(["سجل الحركات التفصيلي", "تقرير المخزون كملف Excel"])

    conn = get_connection()

    with tab1:
        df_trans = pd.read_sql_query(
            """
            SELECT 
                t.id AS 'رقم الحركة',
                t.date AS 'التاريخ',
                p.name AS 'الصنف',
                w.name AS 'المخزن',
                t.trans_type AS 'نوع الحركة',
                t.quantity AS 'الكمية',
                t.user AS 'المستخدم',
                t.notes AS 'ملاحظات'
            FROM transactions t
            JOIN products p ON t.product_code = p.code
            JOIN warehouses w ON t.warehouse_id = w.id
            ORDER BY t.id DESC
        """,
            conn,
        )

        st.dataframe(df_trans, use_container_width=True)

    with tab2:
        st.subheader("📥 استخراج تقرير شامل بصيغة Excel")

        # تجهيز التقرير لتنزيله
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            # sheet 1: المخزون الحالي
            df_inv_full = pd.read_sql_query(
                "SELECT * FROM inventory", conn
            )
            df_inv_full.to_excel(writer, sheet_name="المخزون الحالي", index=False)

            # sheet 2: الأصناف
            df_prod_full = pd.read_sql_query("SELECT * FROM products", conn)
            df_prod_full.to_excel(writer, sheet_name="الأصناف", index=False)

            # sheet 3: سجل الحركات
            df_trans.to_excel(writer, sheet_name="الحركات", index=False)

        st.download_button(
            label="📊 تحميل التقرير الشامل (Excel)",
            data=buffer.getvalue(),
            file_name=f"inventory_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    conn.close()

# ---------------------------------------------------------
# 6. USER MANAGEMENT (ADMIN ONLY)
# ---------------------------------------------------------
elif choice == "إدارة المستخدمين":
    if st.session_state["role"] != "Admin":
        st.error("عذراً، هذه الصفحة للمدير فقط!")
    else:
        st.header("👥 إنشاء وإدارة حسابات المستخدمين")

        with st.form("add_user"):
            col1, col2 = st.columns(2)
            with col1:
                u_name = st.text_input("اسم المستخدم (Username)")
                u_pass = st.text_input("كلمة المرور", type="password")
            with col2:
                u_fullname = st.text_input("الاسم الكامل")
                u_role = st.selectbox("الصلاحية", ["مستخدم عادي", "Admin"])

            submit = st.form_submit_button("إنشاء حساب جديد")

            if submit:
                if not u_name or not u_pass:
                    st.error("يرجى إدخال اسم المستخدم وكلمة المرور!")
                else:
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO users VALUES (?, ?, ?, ?)",
                            (u_name, u_pass, u_role, u_fullname),
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"تم إنشاء حساب للمستخدم {u_fullname} بنجاح!")
                    except sqlite3.IntegrityError:
                        st.error("اسم المستخدم مسجل مسبقاً!")

        st.subheader("👥 الحسابات المسجلة")
        conn = get_connection()
        df_u = pd.read_sql_query(
            "SELECT username AS 'اسم المستخدم', full_name AS 'الاسم', role AS 'الصلاحية' FROM users",
            conn,
        )
        conn.close()
        st.dataframe(df_u, use_container_width=True)