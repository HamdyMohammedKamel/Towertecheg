import streamlit as st
import sqlite3
import pandas as pd
import datetime
import os
import plotly.express as px

# ==========================================
# 1. إعدادات الصفحة والتصميم العام (CSS)
# ==========================================
st.set_page_config(
    page_title="نظام الإدارة والمخازن المتكامل - Smart ERP",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS لشكل القائمة الجانبية والأزرار بدرجات الرمادي واللوجو
st.markdown("""
<style>
    .stApp {
        direction: rtl;
        text-align: right;
    }
    
    [data-testid="stSidebar"] {
        background-color: #f4f5f7;
        padding-top: 10px;
    }
    
    .sidebar-category {
        font-weight: bold;
        color: #333333;
        background-color: #e2e8f0;
        padding: 8px 12px;
        border-radius: 5px;
        margin-top: 15px;
        margin-bottom: 5px;
        font-size: 14px;
        border-right: 4px solid #4a5568;
    }

    .logo-container {
        text-align: center;
        padding: 10px;
        background: linear-gradient(135deg, #2d3748, #1a202c);
        color: white;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    
    .logo-title-ar { font-size: 20px; font-weight: bold; margin: 0; }
    .logo-title-en { font-size: 12px; color: #cbd5e0; margin: 0; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. تهيئة قاعدة البيانات SQLITE (لا تتمسح البيانات)
# ==========================================
DB_FILE = "smart_erp_system.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # جدول المستخدمين والصلاحيات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL
    )
    ''')
    
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, full_name, role) VALUES ('admin', 'admin123', 'مدير النظام', 'Admin')")

    # جدول المخازن
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        location TEXT,
        manager TEXT
    )
    ''')

    # جدول الأصناف
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT,
        serial_number TEXT,
        part_number TEXT,
        min_quantity INTEGER DEFAULT 5,
        unit TEXT DEFAULT 'قطعة',
        cost_price REAL DEFAULT 0,
        selling_price REAL DEFAULT 0,
        description TEXT
    )
    ''')

    # جدول العملاء والموردين
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS partners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        tax_number TEXT,
        balance REAL DEFAULT 0.0
    )
    ''')

    # جدول حركة المخازن
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS inventory_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        trans_type TEXT NOT NULL,
        warehouse_id INTEGER,
        item_id INTEGER,
        quantity INTEGER,
        unit_price REAL,
        partner_id INTEGER,
        person_in_charge TEXT,
        notes TEXT,
        FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
        FOREIGN KEY (item_id) REFERENCES items(id)
    )
    ''')

    # جدول الفواتير
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT UNIQUE NOT NULL,
        date TEXT NOT NULL,
        invoice_type TEXT NOT NULL,
        partner_id INTEGER,
        warehouse_id INTEGER,
        total_amount REAL,
        created_by TEXT,
        FOREIGN KEY (partner_id) REFERENCES partners(id)
    )
    ''')

    # جدول الخزنة والماليات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS treasury (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        trans_type TEXT NOT NULL,
        category TEXT,
        amount REAL NOT NULL,
        statement TEXT,
        user_name TEXT
    )
    ''')

    # جدول البنوك والشيكات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bank_cheques (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_name TEXT NOT NULL,
        cheque_number TEXT NOT NULL,
        cheque_type TEXT NOT NULL,
        partner_id INTEGER,
        amount REAL NOT NULL,
        due_date TEXT NOT NULL,
        status TEXT DEFAULT 'محتفظ به',
        FOREIGN KEY (partner_id) REFERENCES partners(id)
    )
    ''')

    # جدول الموارد البشرية
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hr_employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        emp_name TEXT NOT NULL,
        position TEXT,
        basic_salary REAL,
        advances REAL DEFAULT 0
    )
    ''')

    conn.commit()
    conn.close()

init_db()


# ==========================================
# 3. إدارة الجلسة والدخول Session Management
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user' not in st.session_state:
    st.session_state['user'] = None

def login(username, password):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
    conn.close()
    if user:
        st.session_state['logged_in'] = True
        st.session_state['user'] = dict(user)
        return True
    return False

def logout():
    st.session_state['logged_in'] = False
    st.session_state['user'] = None
    st.rerun()


# ==========================================
# 4. الشاشة الرئيسية والدخول
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="logo-container">
            <h1 class="logo-title-ar">نظام المحاسب والإدارة المالي والمخزني</h1>
            <p class="logo-title-en">SMART ACCOUNTING & INVENTORY SYSTEM</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.subheader("🔑 تسجيل الدخول")
            username = st.text_input("اسم المستخدم")
            password = st.text_input("كلمة السر", type="password")
            submit = st.form_submit_button("دخول", use_container_width=True)
            if submit:
                if login(username, password):
                    st.success("تم تسجيل الدخول بنجاح!")
                    st.rerun()
                else:
                    st.error("اسم المستخدم أو كلمة السر غير صحيحة.")
    st.stop()


# ==========================================
# 5. القائمة الجانبية (الشكل والتنقل)
# ==========================================
user = st.session_state['user']

with st.sidebar:
    st.markdown("""
    <div class="logo-container">
        <div class="logo-title-ar">💼 المحاسب الذكي</div>
        <div class="logo-title-en">SMART ACCOUNTANT ERP</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.write(f"👤 مرحباً: **{user['full_name']}** ({user['role']})")
    if st.button("🚪 تسجيل الخروج", use_container_width=True):
        logout()
    
    st.markdown("---")
    
    menu_choice = None
    
    st.markdown('<div class="sidebar-category">📦 إدارة المخازن والأصناف</div>', unsafe_allow_html=True)
    if user['role'] in ['Admin', 'Storekeeper']:
        if st.button("🏬 إضافة/تعديل مخزن فرعي", use_container_width=True): menu_choice = "المخازن"
        if st.button("🏷️ تكويد صنف جديد", use_container_width=True): menu_choice = "الأصناف"
        if st.button("🔄 حركة مخزنية (إضافة/صرف/مرتجع)", use_container_width=True): menu_choice = "الحركات المخزنية"
    if st.button("📊 جرد ورصيد المخزون الحالي", use_container_width=True): menu_choice = "جرد المخزون"

    st.markdown('<div class="sidebar-category">👥 العملاء والموردين</div>', unsafe_allow_html=True)
    if user['role'] in ['Admin', 'Sales', 'Accountant', 'Storekeeper']:
        if st.button("🤝 تكويد وتعديل عميل / مورد", use_container_width=True): menu_choice = "الشركاء"

    st.markdown('<div class="sidebar-category">🧾 المبيعات والفواتير</div>', unsafe_allow_html=True)
    if user['role'] in ['Admin', 'Sales', 'Accountant', 'Storekeeper']:
        if st.button("📄 إصدار فاتورة مبيعات", use_container_width=True): menu_choice = "إصدار فاتورة"
        if st.button("🔍 استعلام عن الفواتير", use_container_width=True): menu_choice = "استعلام الفواتير"

    st.markdown('<div class="sidebar-category">💰 الحسابات والمالية والخزنة</div>', unsafe_allow_html=True)
    if user['role'] in ['Admin', 'Accountant']:
        if st.button("💵 الخزنة واليومية (وارد/منصرف)", use_container_width=True): menu_choice = "الخزنة والماليات"
        if st.button("🏦 البنوك والشيكات", use_container_width=True): menu_choice = "البنوك والشيكات"

    st.markdown('<div class="sidebar-category">👔 الموارد البشرية HR</div>', unsafe_allow_html=True)
    if user['role'] in ['Admin', 'HR', 'Accountant']:
        if st.button("📋 الموظفين والرواتب والسلف", use_container_width=True): menu_choice = "الموارد البشرية"

    st.markdown('<div class="sidebar-category">📈 التقارير والإحصائيات</div>', unsafe_allow_html=True)
    if st.button("📊 التقارير الشاملة والبيانات", use_container_width=True): menu_choice = "التقارير"
    if user['role'] == 'Admin':
        if st.button("👑 تقارير الإدارة العليا (صاحب الشركة)", use_container_width=True): menu_choice = "تقارير الإدارة العليا"

    if user['role'] == 'Admin':
        st.markdown('<div class="sidebar-category">⚙️ الإعدادات والصلاحيات</div>', unsafe_allow_html=True)
        if st.button("👤 إدارة المستخدمين وكلمات السر", use_container_width=True): menu_choice = "المستخدمين"
        if st.button("💾 النسخ الاحتياطي (Backup/Restore)", use_container_width=True): menu_choice = "النسخ الاحتياطي"

if not menu_choice:
    menu_choice = "المخازن"


# ==========================================
# 6. تفاصيل الشاشات
# ==========================================

# ------------------------------------------
# 1. إدارة المخازن
# ------------------------------------------
if menu_choice == "المخازن":
    st.title("🏬 إدارة المخازن الرئيسية والفرعية")
    
    with st.form("add_warehouse_form", clear_on_submit=True):
        st.subheader("إضافة مخزن جديد")
        w_name = st.text_input("اسم المخزن*")
        w_loc = st.text_input("الموقع / العنوان")
        w_mgr = st.text_input("المسؤول عن المخزن")
        submit_w = st.form_submit_button("حفظ المخزن")
        
        if submit_w:
            if w_name.strip() != "":
                conn = get_db_connection()
                try:
                    conn.execute("INSERT INTO warehouses (name, location, manager) VALUES (?, ?, ?)", (w_name.strip(), w_loc, w_mgr))
                    conn.commit()
                    st.success(f"✅ تم إضافة المخزن '{w_name}' بنجاح!")
                except Exception as e:
                    st.error("❌ اسم المخزن موجود مسبقاً!")
                finally:
                    conn.close()
            else:
                st.warning("⚠️ يرجى كتابة اسم المخزن.")

    st.subheader("📋 قائمة المخازن المسجلة")
    conn = get_db_connection()
    df_w = pd.read_sql("SELECT * FROM warehouses", conn)
    conn.close()
    
    if df_w.empty:
        st.info("💡 لا يوجد مخازن مسجلة حتى الآن. استخدم النموذج أعلاه لإنشاء أول مخزن.")
    else:
        st.dataframe(df_w, use_container_width=True)


# ------------------------------------------
# 2. تكويد صنف جديد
# ------------------------------------------
elif menu_choice == "الأصناف":
    st.title("🏷️ تكويد صنف جديد والتعديل")
    
    with st.form("add_item_form", clear_on_submit=True):
        st.subheader("بيانات الصنف التفصيلية")
        c1, c2, c3 = st.columns(3)
        with c1:
            item_code = st.text_input("كود الصنف (Item Code)*")
            name = st.text_input("اسم الصنف*")
            category = st.text_input("التصنيف (Category)")
        with c2:
            serial_number = st.text_input("السريال (Serial Number)")
            part_number = st.text_input("رقم القطعة (Part Number)")
            unit = st.selectbox("وحدة القياس", ["قطعة", "متر", "طقم", "كرتونة", "جهاز"])
        with c3:
            min_quantity = st.number_input("حد الأمان (الحد الأدنى للكمية)", min_value=0, value=5)
            cost_price = st.number_input("سعر التكلفة / الشراء", min_value=0.0, value=0.0)
            selling_price = st.number_input("سعر البيع", min_value=0.0, value=0.0)
        
        description = st.text_area("وصف إضافي وملاحظات الصنف")
        submit_item = st.form_submit_button("حفظ الصنف")
        
        if submit_item:
            if item_code.strip() != "" and name.strip() != "":
                conn = get_db_connection()
                try:
                    conn.execute("""
                        INSERT INTO items (item_code, name, category, serial_number, part_number, min_quantity, unit, cost_price, selling_price, description)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (item_code.strip(), name.strip(), category, serial_number, part_number, min_quantity, unit, cost_price, selling_price, description))
                    conn.commit()
                    st.success(f"✅ تم حفظ الصنف '{name}' بنجاح!")
                except Exception as e:
                    st.error("❌ كود الصنف مسجل مسبقاً!")
                finally:
                    conn.close()
            else:
                st.warning("⚠️ يرجى كتابة كود الصنف واسم الصنف على الأقل.")

    st.subheader("📋 قائمة الأصناف المسجلة")
    conn = get_db_connection()
    df_items = pd.read_sql("SELECT * FROM items", conn)
    conn.close()
    
    if df_items.empty:
        st.info("💡 لا توجد أصناف مسجلة حتى الآن. استخدم النموذج أعلاه لإنشاء أول صنف.")
    else:
        st.dataframe(df_items, use_container_width=True)


# ------------------------------------------
# 3. الحركات المخزنية
# ------------------------------------------
elif menu_choice == "الحركات المخزنية":
    st.title("🔄 تسجيل حركة مخزنية (إضافة / صرف / مرتجع / تحويل)")
    
    conn = get_db_connection()
    warehouses = pd.read_sql("SELECT * FROM warehouses", conn)
    items = pd.read_sql("SELECT * FROM items", conn)
    partners = pd.read_sql("SELECT * FROM partners", conn)
    conn.close()

    # تشخيص دقيق يمنع التداخل أو التنبيهات المبهمة
    if warehouses.empty and items.empty:
        st.warning("⚠️ لا يمكنك تسجيل حركة حالياً: يرجى أولاً إضافة (مخزن واحد) من شاشة 'المخازن' و (صنف واحد) من شاشة 'الأصناف'.")
    elif warehouses.empty:
        st.warning("⚠️ لا يوجد أي مخزن مسجل! يرجى الذهاب أولاً إلى شاشة '🏬 إضافة/تعديل مخزن فرعي' وإنشاء مخزن.")
    elif items.empty:
        st.warning("⚠️ لا يوجد أي صنف مسجل! يرجى الذهاب أولاً إلى شاشة '🏷️ تكويد صنف جديد' وإضافة صنف.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            trans_type = st.selectbox("نوع الحركة", ["إضافة (مشتريات/وارد)", "صرف (مبيعات/منصرف)", "مرتجع", "تحويل بين المخازن"])
            trans_date = st.date_input("تاريخ الحركة", datetime.date.today())
            selected_item = st.selectbox("اختر الصنف", items['name'].tolist())
            item_id = int(items[items['name'] == selected_item]['id'].values[0])
            
        with c2:
            if trans_type == "تحويل بين المخازن":
                from_wh = st.selectbox("من مخزن (صرف)", warehouses['name'].tolist(), key='from_wh')
                to_wh = st.selectbox("إلى مخزن (إضافة)", [w for w in warehouses['name'].tolist() if w != from_wh], key='to_wh')
            else:
                selected_wh = st.selectbox("المخزن المعني", warehouses['name'].tolist())
                partner_list = ["بدون"] + partners['name'].tolist()
                selected_partner = st.selectbox("العميل / المورد المعني", partner_list)

        c3, c4 = st.columns(2)
        with c3:
            quantity = st.number_input("الكمية", min_value=1, value=1)
            unit_price = st.number_input("السعر التقديري / الفعلي للوحدة", min_value=0.0, value=0.0)
        with c4:
            person_in_charge = st.text_input("اسم المسؤول عن الطلب / المستلم")
            notes = st.text_area("ملاحظات الحركة")

        if st.button("💾 تسجيل الحركة المخزنية"):
            conn = get_db_connection()
            curr = conn.cursor()
            
            p_id = None
            if trans_type != "تحويل بين المخازن" and selected_partner != "بدون":
                p_id = int(partners[partners['name'] == selected_partner]['id'].values[0])

            if trans_type == "تحويل بين المخازن":
                f_id = int(warehouses[warehouses['name'] == from_wh]['id'].values[0])
                t_id = int(warehouses[warehouses['name'] == to_wh]['id'].values[0])
                curr.execute("""
                    INSERT INTO inventory_transactions (date, trans_type, warehouse_id, item_id, quantity, unit_price, person_in_charge, notes)
                    VALUES (?, 'صرف', ?, ?, ?, ?, ?, ?)
                """, (str(trans_date), f_id, item_id, quantity, unit_price, person_in_charge, f"تحويل إلى مخزن {to_wh}: {notes}"))
                
                curr.execute("""
                    INSERT INTO inventory_transactions (date, trans_type, warehouse_id, item_id, quantity, unit_price, person_in_charge, notes)
                    VALUES (?, 'إضافة', ?, ?, ?, ?, ?, ?)
                """, (str(trans_date), t_id, item_id, quantity, unit_price, person_in_charge, f"تحويل من مخزن {from_wh}: {notes}"))
                st.success(f"✅ تم تحويل {quantity} من {from_wh} إلى {to_wh} بنجاح!")
            else:
                w_id = int(warehouses[warehouses['name'] == selected_wh]['id'].values[0])
                clean_type = "إضافة" if "إضافة" in trans_type else ("صرف" if "صرف" in trans_type else "مرتجع")
                curr.execute("""
                    INSERT INTO inventory_transactions (date, trans_type, warehouse_id, item_id, quantity, unit_price, partner_id, person_in_charge, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (str(trans_date), clean_type, w_id, item_id, quantity, unit_price, p_id, person_in_charge, notes))
                st.success("✅ تم تسجيل الحركة المخزنية بنجاح!")

            conn.commit()
            conn.close()


# ------------------------------------------
# 4. جرد ورصيد المخزون
# ------------------------------------------
elif menu_choice == "جرد المخزون":
    st.title("📊 جرد المخزون الحالي والتنبيهات")
    
    conn = get_db_connection()
    query = """
    SELECT 
        i.item_code as 'كود الصنف',
        i.name as 'اسم الصنف',
        w.name as 'المخزن',
        SUM(CASE WHEN t.trans_type = 'إضافة' THEN t.quantity WHEN t.trans_type = 'صرف' THEN -t.quantity WHEN t.trans_type = 'مرتجع' THEN t.quantity ELSE 0 END) as 'الرصيد الحالي',
        i.min_quantity as 'حد الأمان',
        i.cost_price as 'سعر التكلفة',
        (SUM(CASE WHEN t.trans_type = 'إضافة' THEN t.quantity WHEN t.trans_type = 'صرف' THEN -t.quantity WHEN t.trans_type = 'مرتجع' THEN t.quantity ELSE 0 END) * i.cost_price) as 'إجمالي القيمة'
    FROM inventory_transactions t
    JOIN items i ON t.item_id = i.id
    JOIN warehouses w ON t.warehouse_id = w.id
    GROUP BY i.id, w.id
    """
    df_stock = pd.read_sql(query, conn)
    conn.close()

    if not df_stock.empty:
        low_stock = df_stock[df_stock['الرصيد الحالي'] <= df_stock['حد الأمان']]
        if not low_stock.empty:
            st.error("⚠️ **تنبيـــه: يوجد أصناف وصلت إلى حد الأمان أو أقل!**")
            st.dataframe(low_stock, use_container_width=True)

        st.subheader("جدول جرد المخزون")
        st.dataframe(df_stock, use_container_width=True)
        st.metric("إجمالي قيمة البضاعة بالمخازن", f"{df_stock['إجمالي القيمة'].sum():,.2f} ج.م")
    else:
        st.info("💡 لا توجد حركات مخزنية أو أرصدة مسجلة حتى الآن. (قم بتسجيل حركات إضافة أولاً من شاشة الحركات المخزنية).")


# ------------------------------------------
# 5. العملاء والموردين
# ------------------------------------------
elif menu_choice == "الشركاء":
    st.title("🤝 إدارة العملاء والموردين وتعديلهم")
    
    with st.form("partner_form", clear_on_submit=True):
        st.subheader("إضافة شريك جديد")
        p_name = st.text_input("الاسم الكامل (شركة / فرد)*")
        p_type = st.selectbox("الصفة", ["عميل", "مورد", "عميل ومورد معا (Dual Role)", "مخزن محلي"])
        p_phone = st.text_input("رقم الهاتف")
        p_address = st.text_input("العنوان")
        p_tax = st.text_input("الرقم الضريبي")
        
        if st.form_submit_button("حفظ الشريك"):
            if p_name.strip() != "":
                conn = get_db_connection()
                conn.execute("INSERT INTO partners (name, type, phone, address, tax_number) VALUES (?, ?, ?, ?, ?)",
                             (p_name.strip(), p_type, p_phone, p_address, p_tax))
                conn.commit()
                conn.close()
                st.success("✅ تم حفظ الشريك بنجاح!")

    st.subheader("قائمة العملاء والموردين المكودين")
    conn = get_db_connection()
    df_p = pd.read_sql("SELECT * FROM partners", conn)
    conn.close()
    st.dataframe(df_p, use_container_width=True)


# ------------------------------------------
# 6. إصدار الفواتير
# ------------------------------------------
elif menu_choice == "إصدار فاتورة":
    st.title("📄 إصدار فاتورة مبيعات")
    
    conn = get_db_connection()
    partners = pd.read_sql("SELECT * FROM partners WHERE type IN ('عميل', 'عميل ومورد معا (Dual Role)')", conn)
    warehouses = pd.read_sql("SELECT * FROM warehouses", conn)
    items = pd.read_sql("SELECT * FROM items", conn)
    conn.close()

    if partners.empty or items.empty:
        st.warning("⚠️ يرجى تأكيد وجود عملاء وأصناف مكودة أولاً قبل اصدار الفاتورة.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            inv_num = st.text_input("رقم الفاتورة", value=f"INV-{int(datetime.datetime.now().timestamp())}")
            inv_date = st.date_input("تاريخ الفاتورة", datetime.date.today())
        with c2:
            selected_partner = st.selectbox("العميل", partners['name'].tolist())
            selected_wh = st.selectbox("صرف من مخزن", warehouses['name'].tolist())
        with c3:
            selected_item = st.selectbox("الصنف", items['name'].tolist())
            qty = st.number_input("الكمية", min_value=1, value=1)

        item_row = items[items['name'] == selected_item].iloc[0]
        price = st.number_input("سعر البيع للوحدة", value=float(item_row['selling_price']))
        total = qty * price

        st.markdown(f"### الإجمالي: **{total:,.2f} ج.م**")

        if st.button("🪶 إصدار وطباعة الفاتورة"):
            conn = get_db_connection()
            curr = conn.cursor()
            p_id = int(partners[partners['name'] == selected_partner]['id'].values[0])
            w_id = int(warehouses[warehouses['name'] == selected_wh]['id'].values[0])
            
            curr.execute("INSERT INTO invoices (invoice_number, date, invoice_type, partner_id, warehouse_id, total_amount, created_by) VALUES (?, ?, 'مبيعات', ?, ?, ?, ?)",
                         (inv_num, str(inv_date), p_id, w_id, total, user['full_name']))
            
            curr.execute("""
                INSERT INTO inventory_transactions (date, trans_type, warehouse_id, item_id, quantity, unit_price, partner_id, person_in_charge, notes)
                VALUES (?, 'صرف', ?, ?, ?, ?, ?, ?, ?)
            """, (str(inv_date), w_id, int(item_row['id']), qty, price, p_id, user['full_name'], f"فاتورة مبيعات رقم {inv_num}"))

            curr.execute("INSERT INTO treasury (date, trans_type, category, amount, statement, user_name) VALUES (?, 'إيراد / وارد', 'فواتير مبيعات', ?, ?, ?)",
                         (str(inv_date), total, f"تحصيل فاتورة رقم {inv_num}", user['full_name']))

            conn.commit()
            conn.close()

            st.success("✅ تم إصدار الفاتورة وتخصيم الكمية من المخزن وتسجيل الإيراد!")


# ------------------------------------------
# 7. استعلام الفواتير
# ------------------------------------------
elif menu_choice == "استعلام الفواتير":
    st.title("🔍 استعلام عن الفواتير الصادرة")
    conn = get_db_connection()
    df_inv = pd.read_sql("""
        SELECT i.invoice_number as 'رقم الفاتورة', i.date as 'التاريخ', i.invoice_type as 'النوع', p.name as 'الشريك', i.total_amount as 'الإجمالي', i.created_by as 'المُصدر'
        FROM invoices i
        LEFT JOIN partners p ON i.partner_id = p.id
    """, conn)
    conn.close()
    st.dataframe(df_inv, use_container_width=True)


# ------------------------------------------
# 8. الخزنة والماليات
# ------------------------------------------
elif menu_choice == "الخزنة والماليات":
    st.title("💰 إدارة الخزنة والمقبوضات والمصروفات")
    
    with st.form("treasury_form", clear_on_submit=True):
        st.subheader("تسجيل حركة مالية")
        c1, c2 = st.columns(2)
        with c1:
            t_type = st.selectbox("نوع الحركة", ["إيراد / وارد", "مصروف / منصرف"])
            t_cat = st.selectbox("البند / التصنيف", ["فواتير", "نثريات مصنع/مكتب", "رواتب موظفين", "مشتريات بضاعة", "أخرى"])
            t_amount = st.number_input("المبلغ", min_value=0.1, value=100.0)
        with c2:
            t_date = st.date_input("التاريخ", datetime.date.today())
            t_statement = st.text_area("البيان / التفاصيل")
            
        if st.form_submit_button("حفظ الحركة المالية"):
            conn = get_db_connection()
            conn.execute("INSERT INTO treasury (date, trans_type, category, amount, statement, user_name) VALUES (?, ?, ?, ?, ?, ?)",
                         (str(t_date), t_type, t_cat, t_amount, t_statement, user['full_name']))
            conn.commit()
            conn.close()
            st.success("✅ تم تسجيل الحركة بالخزنة!")

    st.subheader("كشف حساب حركة الخزنة")
    conn = get_db_connection()
    df_t = pd.read_sql("SELECT * FROM treasury ORDER BY id DESC", conn)
    conn.close()
    
    if not df_t.empty:
        total_in = df_t[df_t['trans_type'] == 'إيراد / وارد']['amount'].sum()
        total_out = df_t[df_t['trans_type'] == 'مصروف / منصرف']['amount'].sum()
        balance = total_in - total_out
        
        c1, c2, c3 = st.columns(3)
        c1.metric("إجمالي المقبوضات (الوارد)", f"{total_in:,.2f} ج.م")
        c2.metric("إجمالي المصروفات (المنصرف)", f"{total_out:,.2f} ج.م")
        c3.metric("رصيد الخزنة الحالي", f"{balance:,.2f} ج.م")
        
        st.dataframe(df_t, use_container_width=True)


# ------------------------------------------
# 9. البنوك والشيكات
# ------------------------------------------
elif menu_choice == "البنوك والشيكات":
    st.title("🏦 قسم الحسابات والشيكات البنكية")
    
    conn = get_db_connection()
    partners = pd.read_sql("SELECT * FROM partners", conn)
    conn.close()

    with st.form("cheque_form", clear_on_submit=True):
        st.subheader("تسجيل شيك بنكي جديد")
        c1, c2 = st.columns(2)
        with c1:
            bank_name = st.text_input("اسم البنك")
            cheque_num = st.text_input("رقم الشيك")
            cheque_type = st.selectbox("نوع الشيك", ["صادر (لمورد)", "وارد (من عميل)"])
        with c2:
            partner_sel = st.selectbox("الشريك المعني", partners['name'].tolist() if not partners.empty else ["بدون"])
            amount = st.number_input("مبلغ الشيك", min_value=1.0)
            due_date = st.date_input("تاريخ الاستحقاق")

        if st.form_submit_button("حفظ الشيك"):
            conn = get_db_connection()
            p_id = int(partners[partners['name'] == partner_sel]['id'].values[0]) if not partners.empty else None
            conn.execute("INSERT INTO bank_cheques (bank_name, cheque_number, cheque_type, partner_id, amount, due_date) VALUES (?, ?, ?, ?, ?, ?)",
                         (bank_name, cheque_num, cheque_type, p_id, amount, str(due_date)))
            conn.commit()
            conn.close()
            st.success("✅ تم تسجيل الشيك البنكي بنجاح!")

    st.subheader("سجل الشيكات البنكية")
    conn = get_db_connection()
    df_c = pd.read_sql("""
        SELECT c.bank_name as 'البنك', c.cheque_number as 'رقم الشيك', c.cheque_type as 'النوع', p.name as 'الشريك', c.amount as 'المبلغ', c.due_date as 'تاريخ الاستحقاق', c.status as 'الحالة'
        FROM bank_cheques c
        LEFT JOIN partners p ON c.partner_id = p.id
    """, conn)
    conn.close()
    st.dataframe(df_c, use_container_width=True)


# ------------------------------------------
# 10. الموارد البشرية HR
# ------------------------------------------
elif menu_choice == "الموارد البشرية":
    st.title("👔 قسم الموارد البشرية HR والرواتب")
    
    tab1, tab2 = st.tabs(["إضافة موظف جديد", "تسجيل سلفة / صرف راتب"])
    
    with tab1:
        with st.form("add_emp", clear_on_submit=True):
            e_name = st.text_input("اسم الموظف")
            e_pos = st.text_input("المسمى الوظيفي")
            e_sal = st.number_input("الراتب الأساسي", min_value=0.0)
            if st.form_submit_button("حفظ الموظف"):
                conn = get_db_connection()
                conn.execute("INSERT INTO hr_employees (emp_name, position, basic_salary) VALUES (?, ?, ?)", (e_name, e_pos, e_sal))
                conn.commit()
                conn.close()
                st.success("✅ تمت إضافة الموظف!")

    with tab2:
        conn = get_db_connection()
        emps = pd.read_sql("SELECT * FROM hr_employees", conn)
        conn.close()
        
        if not emps.empty:
            sel_emp = st.selectbox("اختر الموظف", emps['emp_name'].tolist())
            adv_amount = st.number_input("مبلغ السلفة / العهدة", min_value=0.0)
            if st.button("تسجيل السلفة وخصمها من الخزنة"):
                conn = get_db_connection()
                conn.execute("UPDATE hr_employees SET advances = advances + ? WHERE emp_name = ?", (adv_amount, sel_emp))
                conn.execute("INSERT INTO treasury (date, trans_type, category, amount, statement, user_name) VALUES (?, 'مصروف / منصرف', 'رواتب موظفين', ?, ?, ?)",
                             (str(datetime.date.today()), adv_amount, f"سلفة للموظف {sel_emp}", user['full_name']))
                conn.commit()
                conn.close()
                st.success("✅ تم تسجيل السلفة وخصم المبلغ من الخزنة!")

    st.subheader("سجل الموظفين والرواتب")
    conn = get_db_connection()
    df_e = pd.read_sql("SELECT * FROM hr_employees", conn)
    conn.close()
    st.dataframe(df_e, use_container_width=True)


# ------------------------------------------
# 11. التقارير والبيانات
# ------------------------------------------
elif menu_choice == "التقارير":
    st.title("📈 مركز التقارير الشاملة")
    
    conn = get_db_connection()
    st.subheader("📊 رسم بياني للرسوم والحركات")
    df_m = pd.read_sql("SELECT trans_type, COUNT(*) as count FROM inventory_transactions GROUP BY trans_type", conn)
    if not df_m.empty:
        fig2 = px.bar(df_m, x='trans_type', y='count', title='عدد الحركات المخزنية حسب النوع', color='trans_type')
        st.plotly_chart(fig2, use_container_width=True)
    
    st.subheader("سجل كل الحركات المخزنية")
    df_all = pd.read_sql("SELECT * FROM inventory_transactions", conn)
    st.dataframe(df_all, use_container_width=True)
    conn.close()


# ------------------------------------------
# 12. تقارير الإدارة العليا
# ------------------------------------------
elif menu_choice == "تقارير الإدارة العليا":
    st.title("👑 لوحة قيادة الإدارة العليا")
    
    conn = get_db_connection()
    st.subheader("🏆 إجمالي التعاملات المالية للعملاء والموردين")
    df_p = pd.read_sql("""
        SELECT p.name as 'الاسم', p.type as 'النوع', SUM(i.total_amount) as 'إجمالي الفواتير'
        FROM invoices i
        JOIN partners p ON i.partner_id = p.id
        GROUP BY p.id
    """, conn)
    st.dataframe(df_p, use_container_width=True)
    conn.close()


# ------------------------------------------
# 13. إدارة المستخدمين
# ------------------------------------------
elif menu_choice == "المستخدمين":
    st.title("👤 إدارة المستخدمين والصلاحيات")
    
    with st.form("add_user_form", clear_on_submit=True):
        st.subheader("إنشاء حساب موظف جديد")
        u_name = st.text_input("اسم المستخدم (Username)*")
        u_pass = st.text_input("كلمة السر*", type="password")
        u_full = st.text_input("الاسم الكامل للموظف*")
        u_role = st.selectbox("الدور / الصلاحية", ["Admin", "Storekeeper", "Sales", "Accountant", "HR"])
        
        if st.form_submit_button("إنشاء الحساب"):
            if u_name and u_pass:
                conn = get_db_connection()
                try:
                    conn.execute("INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
                                 (u_name, u_pass, u_full, u_role))
                    conn.commit()
                    st.success("✅ تم إنشاء حساب الموظف بنجاح!")
                except:
                    st.error("❌ اسم المستخدم مسجل مسبقاً")
                finally:
                    conn.close()

    st.subheader("قائمة المستخدمين بالنظام")
    conn = get_db_connection()
    df_u = pd.read_sql("SELECT id, username, full_name, role FROM users", conn)
    conn.close()
    st.dataframe(df_u, use_container_width=True)


# ------------------------------------------
# 14. النسخ الاحتياطي Restore / Backup
# ------------------------------------------
elif menu_choice == "النسخ الاحتياطي":
    st.title("💾 إدارة النسخ الاحتياطي واسترجاع البيانات")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📦 أخذ نسخة احتياطية (Backup)")
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "rb") as f:
                bytes_data = f.read()
            st.download_button(
                label="⬇️ اضغط هنا لتنزيل ملف Backup",
                data=bytes_data,
                file_name=f"backup_smart_erp_{datetime.date.today()}.db",
                mime="application/x-sqlite3"
            )

    with col2:
        st.subheader("♻️ استرجاع نسخة قديمة (Restore)")
        uploaded_file = st.file_uploader("اختر ملف قاعدة البيانات Backup (.db)", type=["db"])
        if uploaded_file is not None:
            if st.button("⚠️ تأكيد استرجاع البيانات وإعادة الكتابة"):
                with open(DB_FILE, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success("✅ تم استرجاع قاعدة البيانات بنجاح! يرجى إعادة تحميل الصفحة.")