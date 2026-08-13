import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib
import io
import os
import plotly.express as px

# ==========================================
# 1. تهيئة الصفحة والـ CSS للهوية البصرية
# ==========================================
st.set_page_config(
    page_title="المحاسب | AL-MOHASEB ERP",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: RTL;
        text-align: right;
    }
    
    /* شريط العنوان والهوية البصرية لشركة حاسبات */
    .brand-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 2px solid #38bdf8;
        color: #ffffff;
        padding: 18px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(56, 189, 248, 0.20);
    }
    .brand-logo {
        font-size: 28px;
        font-weight: 800;
        color: #38bdf8;
        letter-spacing: 1px;
    }
    .brand-subtitle {
        font-size: 14px;
        color: #94a3b8;
        margin-top: 4px;
    }

    /* الشريط الجانبي بالرمادي الفاتح مع فواصل وأزرار واضحة */
    [data-testid="stSidebar"] {
        background-color: #f1f5f9 !important;
        border-left: 1px solid #cbd5e1;
    }
    .sidebar-section-title {
        background-color: #e2e8f0;
        color: #0f172a;
        font-weight: 700;
        font-size: 14px;
        padding: 8px 12px;
        border-radius: 6px;
        margin-top: 15px;
        margin-bottom: 8px;
        border-right: 4px solid #0284c7;
    }
    .sidebar-divider {
        margin: 12px 0;
        border-bottom: 1px dashed #cbd5e1;
    }

    /* تنسيق الطباعة A4 */
    @media print {
        body * { visibility: hidden; }
        .printable-area, .printable-area * { visibility: visible; }
        .printable-area {
            position: absolute; left: 0; top: 0; width: 100%;
            padding: 20px; font-size: 14px; color: #000; background: #fff;
        }
        .no-print { display: none !important; }
    }
    
    .stButton>button {
        border-radius: 6px; font-weight: 700;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. إدارة قاعدة البيانات SQLite (دائمة)
# ==========================================
DB_FILE = "almohaseb_erp.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # جدول المستخدمين والصلاحيات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'مسؤول مخازن',
            assigned_warehouse_id INTEGER DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول المخازن/الفروع
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warehouses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            location TEXT,
            is_main INTEGER DEFAULT 0
        )
    ''')
    
    # جدول الشركاء (عميل / مورد / عميل ومورد)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            phone TEXT,
            partner_type TEXT NOT NULL,
            address TEXT,
            notes TEXT
        )
    ''')
    
    # جدول الأصناف
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            part_number TEXT,
            serial_number TEXT,
            name TEXT NOT NULL,
            category TEXT,
            unit TEXT DEFAULT 'قطعة',
            main_supplier_id INTEGER,
            min_quantity INTEGER DEFAULT 3,
            cost_price REAL DEFAULT 0.0,
            selling_price REAL DEFAULT 0.0,
            image_url TEXT,
            notes TEXT,
            FOREIGN KEY (main_supplier_id) REFERENCES partners(id)
        )
    ''')
    
    # جدول أرصده المخزون
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER,
            item_id INTEGER,
            quantity INTEGER DEFAULT 0,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (item_id) REFERENCES items(id),
            UNIQUE(warehouse_id, item_id)
        )
    ''')
    
    # جدول حركات المخزون والتحويلات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trans_date DATE NOT NULL,
            trans_type TEXT NOT NULL, 
            warehouse_id INTEGER NOT NULL,
            dest_warehouse_id INTEGER DEFAULT NULL,
            item_id INTEGER NOT NULL,
            partner_id INTEGER,
            requester_name TEXT,
            quantity INTEGER NOT NULL,
            unit_price REAL DEFAULT 0.0,
            total_price REAL DEFAULT 0.0,
            reference_no TEXT,
            notes TEXT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول الفواتير
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT UNIQUE NOT NULL,
            invoice_date DATE NOT NULL,
            partner_id INTEGER NOT NULL,
            warehouse_id INTEGER NOT NULL,
            sales_rep_id INTEGER NOT NULL,
            total_amount REAL DEFAULT 0.0,
            tax_amount REAL DEFAULT 0.0,
            net_amount REAL DEFAULT 0.0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # بنود الفواتير
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL
        )
    ''')
    
    # جدول الحسابات النقدية والخزينة
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS treasury_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date DATE NOT NULL,
            warehouse_id INTEGER NOT NULL,
            entry_type TEXT NOT NULL, 
            partner_id INTEGER DEFAULT NULL,
            amount REAL NOT NULL,
            statement TEXT NOT NULL,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # إنشاء المخزن الرئيسي والحسابات الافتراضية
    cursor.execute("SELECT * FROM warehouses WHERE is_main = 1")
    main_wh = cursor.fetchone()
    if not main_wh:
        cursor.execute("INSERT INTO warehouses (name, location, is_main) VALUES ('المخزن الرئيسي (HQ)', 'الفرع الرئيسي', 1)")
        main_wh_id = cursor.lastrowid
    else:
        main_wh_id = main_wh['id']
        
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, full_name, role, assigned_warehouse_id) VALUES (?, ?, ?, ?, ?)",
            ('admin', hash_password('admin123'), 'مدير النظام العام', 'مدير النظام', main_wh_id)
        )
        
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 3. الهيدر العام والشعار
# ==========================================
def render_brand_header():
    st.markdown("""
        <div class="brand-header">
            <div class="brand-logo">💻 برنامج المحاسب | AL-MOHASEB ERP ⚡</div>
            <div class="brand-subtitle">نظام المبيعات وإدارة المخازن المتعددة والخزينة المالي الموحد - حلول تكنولوجيا المعلومات</div>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# 4. تسجيل الدخول واختيار الجلسة
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ''
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = ''
if 'full_name' not in st.session_state:
    st.session_state['full_name'] = ''
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
if 'user_wh_id' not in st.session_state:
    st.session_state['user_wh_id'] = None

def login_screen():
    render_brand_header()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔑 تسجيل الدخول للتطبيق")
        username_input = st.text_input("اسم المستخدم")
        password_input = st.text_input("كلمة السر", type="password")
        
        if st.button("تسجيل الدخول"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, full_name, role, assigned_warehouse_id FROM users WHERE username = ? AND password = ?",
                (username_input, hash_password(password_input))
            )
            user = cursor.fetchone()
            conn.close()
            
            if user:
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = user['id']
                st.session_state['username'] = user['username']
                st.session_state['full_name'] = user['full_name']
                st.session_state['user_role'] = user['role']
                st.session_state['user_wh_id'] = user['assigned_warehouse_id']
                st.success(f"مرحباً بك، {user['full_name']} [{user['role']}]")
                st.rerun()
            else:
                st.error("بيانات الدخول غير صحيحة")

if not st.session_state['logged_in']:
    login_screen()
    st.stop()

# ==========================================
# 5. القائمة الجانبية المنظمة بأسلوب الأقسام
# ==========================================
role = st.session_state['user_role']
user_wh_id = st.session_state['user_wh_id']

with st.sidebar:
    st.markdown("### 💻 برنامج المحاسب")
    st.write(f"👤 **المستخدم:** {st.session_state['full_name']}")
    st.write(f"💼 **الصلاحية:** `{role}`")
    
    st.markdown("<div class='sidebar-divider'></div>", unsafe_allow_html=True)
    
    options_map = {}
    
    # قسم المخزون والتكويد
    options_map["--- المخزون والتكويد ---"] = []
    options_map["--- المخزون والتكويد ---"].append("📊 جرد المخزون والتنبيهات")
    if role in ['مدير النظام', 'مسؤول مخازن']:
        options_map["--- المخزون والتكويد ---"].append("🏷️ إضافة وتعديل الأصناف")
        options_map["--- المخزون والتكويد ---"].append("🤝 إدارة وتعديل العملاء والموردين")
        options_map["--- المخزون والتكويد ---"].append("📝 أذون الحركة (إضافة / صرف / مرتجع)")
        options_map["--- المخزون والتكويد ---"].append("🔄 التحويل بين المخازن")
        options_map["--- المخزون والتكويد ---"].append("🏭 إدارة المخازن والفروع")
        
    # قسم المبيعات والفواتير
    options_map["--- المبيعات والفواتير ---"] = []
    if role in ['مدير النظام', 'ممثل مبيعات']:
        options_map["--- المبيعات والفواتير ---"].append("🧾 إصدار فاتورة بيع A4")
    options_map["--- المبيعات والفواتير ---"].append("🔍 استعلام وشاشة الفواتير")

    # قسم الحسابات والخزينة
    options_map["--- المالية والحسابات ---"] = []
    if role in ['مدير النظام', 'محاسب']:
        options_map["--- المالية والحسابات ---"].append("💰 حركة الخزنة والنثريات")
        options_map["--- المالية والحسابات ---"].append("📈 تقرير الأرباح والخسائر وكشف الحساب")

    # قسم التقارير والإدارة
    options_map["--- التقارير والإدارة ---"] = []
    options_map["--- التقارير والإدارة ---"].append("📜 التقارير التشغيلية والاستعلامات")
    options_map["--- التقارير والإدارة ---"].append("👑 تقارير الإدارة الاستراتيجية")
    if role == 'مدير النظام':
        options_map["--- التقارير والإدارة ---"].append("⚙️ إدارة المستخدمين والصلاحيات")
        options_map["--- التقارير والإدارة ---"].append("💾 النسخ الاحتياطي والاستعادة")

    for sec_title, sec_opts in options_map.items():
        if sec_opts:
            st.markdown(f"<div class='sidebar-section-title'>{sec_title}</div>", unsafe_allow_html=True)
            for opt in sec_opts:
                if st.button(opt, key=f"btn_{opt}"):
                    st.session_state['current_page'] = opt

    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = "📊 جرد المخزون والتنبيهات"
        
    choice = st.session_state['current_page']
    
    st.markdown("<div class='sidebar-divider'></div>", unsafe_allow_html=True)
    if st.button("🚪 تسجيل الخروج"):
        st.session_state['logged_in'] = False
        st.rerun()

render_brand_header()

# ==========================================
# 6. جرد المخزون والتنبيهات
# ==========================================
if choice == "📊 جرد المخزون والتنبيهات":
    st.title("📊 جرد المخزون والتنبيهات الحالية")
    conn = get_connection()
    wh_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    wh_options = {"جميع المخازن": None}
    for _, r in wh_df.iterrows():
        wh_options[r['name']] = r['id']
        
    sel_wh = st.selectbox("تصفية حسب المخزن:", list(wh_options.keys()))
    sel_wh_id = wh_options[sel_wh]
    
    query = """
        SELECT 
            w.name AS 'المخزن', i.code AS 'الكود', i.part_number AS 'Part Number',
            i.serial_number AS 'S/N', i.name AS 'اسم الصنف', i.category AS 'الفئة',
            COALESCE(inv.quantity, 0) AS 'الكمية المتاحة', i.min_quantity AS 'الحد الأدنى',
            i.cost_price AS 'سعر التكلفة', i.selling_price AS 'سعر البيع'
        FROM items i
        CROSS JOIN warehouses w
        LEFT JOIN inventory inv ON inv.item_id = i.id AND inv.warehouse_id = w.id
    """
    if sel_wh_id:
        query += f" WHERE w.id = {sel_wh_id}"
        
    df_stock = pd.read_sql_query(query, conn)
    low_stock = df_stock[df_stock['الكمية المتاحة'] <= df_stock['الحد الأدنى']]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("إجمالي الأصناف", len(df_stock['الكود'].unique()))
    c2.metric("إجمالي القطع بالمخزن", int(df_stock['الكمية المتاحة'].sum()))
    c3.metric("أصناف بلغت الحد الأدنى", len(low_stock), delta_color="inverse")
    
    if not low_stock.empty:
        st.warning(f"⚠️ تنبيه: يوجد {len(low_stock)} صنف بلغت الحد الأدنى المطلوب للتوريد.")
        st.dataframe(low_stock, use_container_width=True)
        
    st.dataframe(df_stock, use_container_width=True)
    conn.close()

# ==========================================
# 7. إضافة وتعديل الأصناف
# ==========================================
elif choice == "🏷️ إضافة وتعديل الأصناف":
    st.title("🏷️ إدارة وتكويد الأصناف (إضافة / تعديل)")
    conn = get_connection()
    
    tab1, tab2 = st.tabs(["➕ إضافة صنف جديد", "✏️ تعديل صنف موجود"])
    
    with tab1:
        suppliers_df = pd.read_sql_query("SELECT id, name FROM partners WHERE partner_type IN ('مورد', 'عميل ومورد')", conn)
        with st.form("add_item_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            item_code = c1.text_input("كود الصنف*")
            part_number = c2.text_input("Part Number")
            serial_number = c3.text_input("Serial Number (S/N)")
            
            item_name = c1.text_input("اسم الصنف*")
            category = c2.selectbox("التصنيف", ["معالجات", "كروت شاشة", "شبكات وسيرفرات", "شاشات", "أخرى"])
            unit = c3.selectbox("الوحدة", ["قطعة", "متر", "طقم", "جهاز"])
            
            min_qty = c1.number_input("الحد الأدنى للتنبيه", value=3)
            cost_price = c2.number_input("سعر التكلفة", value=0.0)
            selling_price = c3.number_input("سعر البيع", value=0.0)
            
            sup_opts = {"غير محدد": None}
            for _, r in suppliers_df.iterrows():
                sup_opts[r['name']] = r['id']
            main_sup = st.selectbox("المورد الرئيسي", list(sup_opts.keys()))
            image_url = st.text_input("رابط الصورة (URL)")
            notes = st.text_area("ملاحظات")
            
            if st.form_submit_button("حفظ الصنف الجديد"):
                if item_code and item_name:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO items (code, part_number, serial_number, name, category, unit, main_supplier_id, min_quantity, cost_price, selling_price, image_url, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (item_code, part_number, serial_number, item_name, category, unit, sup_opts[main_sup], min_qty, cost_price, selling_price, image_url, notes))
                        conn.commit()
                        st.success("تم الحفظ بنجاح!")
                    except:
                        st.error("الكود مسجل مسبقاً.")
                        
    with tab2:
        items_df = pd.read_sql_query("SELECT id, code, name FROM items", conn)
        if not items_df.empty:
            sel_item_str = st.selectbox("اختر الصنف للتعديل:", items_df.apply(lambda r: f"{r['code']} - {r['name']}", axis=1).tolist())
            item_id = int(items_df[items_df.apply(lambda r: f"{r['code']} - {r['name']}", axis=1) == sel_item_str]['id'].values[0])
            
            item_row = pd.read_sql_query("SELECT * FROM items WHERE id = ?", conn, params=(item_id,)).iloc[0]
            
            with st.form("edit_item_form"):
                e_name = st.text_input("اسم الصنف", value=item_row['name'])
                e_pn = st.text_input("Part Number", value=item_row['part_number'] or '')
                e_sn = st.text_input("Serial Number", value=item_row['serial_number'] or '')
                e_cost = st.number_input("سعر التكلفة", value=float(item_row['cost_price']))
                e_sell = st.number_input("سعر البيع", value=float(item_row['selling_price']))
                e_min = st.number_input("الحد الأدنى", value=int(item_row['min_quantity']))
                
                if st.form_submit_button("تحديث بيانات الصنف"):
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE items SET name=?, part_number=?, serial_number=?, cost_price=?, selling_price=?, min_quantity=? WHERE id=?
                    """, (e_name, e_pn, e_sn, e_cost, e_sell, e_min, item_id))
                    conn.commit()
                    st.success("تم تعديل الصنف بنجاح!")
    conn.close()

# ==========================================
# 8. إدارة وتعديل العملاء والموردين
# ==========================================
elif choice == "🤝 إدارة وتعديل العملاء والموردين":
    st.title("🤝 إدارة وتعديل العملاء والموردين")
    conn = get_connection()
    tab1, tab2 = st.tabs(["➕ إضافة جهة جديدة", "✏️ تعديل جهة مسجلة"])
    
    with tab1:
        with st.form("add_partner_form", clear_on_submit=True):
            p_name = st.text_input("اسم الجهة / الشريك*")
            p_type = st.selectbox("نوع التعامل*", ["عميل", "مورد", "عميل ومورد"])
            p_phone = st.text_input("الهاتف")
            p_address = st.text_input("العنوان")
            p_notes = st.text_area("ملاحظات")
            if st.form_submit_button("حفظ الجهة"):
                if p_name:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO partners (name, partner_type, phone, address, notes) VALUES (?, ?, ?, ?, ?)",
                                       (p_name.strip(), p_type, p_phone.strip(), p_address.strip(), p_notes))
                        conn.commit()
                        st.success("تم التكويد بنجاح!")
                    except:
                        st.error("الاسم مكرر.")
                        
    with tab2:
        partners_df = pd.read_sql_query("SELECT id, name, partner_type, phone, address, notes FROM partners", conn)
        if not partners_df.empty:
            sel_p_name = st.selectbox("اختر الجهة للتعديل:", partners_df['name'].tolist())
            p_row = partners_df[partners_df['name'] == sel_p_name].iloc[0]
            
            with st.form("edit_p_form"):
                e_p_name = st.text_input("الاسم", value=p_row['name'])
                e_p_type = st.selectbox("التصنيف", ["عميل", "مورد", "عميل ومورد"], index=["عميل", "مورد", "عميل ومورد"].index(p_row['partner_type']))
                e_p_phone = st.text_input("الهاتف", value=p_row['phone'] or '')
                e_p_address = st.text_input("العنوان", value=p_row['address'] or '')
                e_p_notes = st.text_area("ملاحظات", value=p_row['notes'] or '')
                
                if st.form_submit_button("تحديث بيانات الشريك"):
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE partners SET name=?, partner_type=?, phone=?, address=?, notes=? WHERE id=?
                    """, (e_p_name, e_p_type, e_p_phone, e_p_address, e_p_notes, p_row['id']))
                    conn.commit()
                    st.success("تم تحديث البيانات بنجاح!")
                    st.rerun()
                    
    st.subheader("📋 قائمة الجهات والشركاء المسجلة")
    st.dataframe(pd.read_sql_query("SELECT id, name AS 'الاسم', partner_type AS 'التصنيف', phone AS 'الهاتف', address AS 'العنوان' FROM partners", conn), use_container_width=True)
    conn.close()

# ==========================================
# 9. أذون الحركة (إضافة / صرف / مرتجع)
# ==========================================
elif choice == "📝 أذون الحركة (إضافة / صرف / مرتجع)":
    st.title("📝 تسجيل أذون الحركة المخزنية")
    conn = get_connection()
    wh_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    items_df = pd.read_sql_query("SELECT id, code, name FROM items", conn)
    partners_df = pd.read_sql_query("SELECT id, name, partner_type FROM partners", conn)
    
    with st.form("trans_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        trans_date = c1.date_input("تاريخ الحركة*", value=datetime.date.today())
        trans_type = c2.selectbox("نوع الحركة*", ["إضافة/توريد", "صرف", "مرتجع"])
        wh_name = c3.selectbox("المخزن*", wh_df['name'].tolist())
        
        item_disp = c1.selectbox("الصنف*", items_df.apply(lambda r: f"{r['code']} - {r['name']}", axis=1).tolist())
        partner_opts = ["عام / غير محدد"] + partners_df.apply(lambda r: f"{r['id']} - {r['name']} ({r['partner_type']})", axis=1).tolist()
        selected_p = c2.selectbox("الجهة*", partner_opts)
        requester_name = c3.text_input("اسم المسؤول عن طلب الصرف / المستلم*")
        
        quantity = c1.number_input("الكمية*", min_value=1, value=1)
        unit_price = c2.number_input("سعر الوحدة*", min_value=0.0, value=0.0)
        reference_no = c3.text_input("رقم الإذن / المرجع")
        
        if st.form_submit_button("تنفيذ الحركة"):
            item_id = items_df[items_df['code'] == item_disp.split(" - ")[0]]['id'].values[0]
            wh_id = wh_df[wh_df['name'] == wh_name]['id'].values[0]
            partner_id = int(selected_p.split(" - ")[0]) if selected_p != "عام / غير محدد" else None
            total_price = quantity * unit_price
            
            cursor = conn.cursor()
            cursor.execute("SELECT quantity FROM inventory WHERE warehouse_id = ? AND item_id = ?", (wh_id, item_id))
            res = cursor.fetchone()
            curr_qty = res['quantity'] if res else 0
            
            if trans_type == "صرف" and quantity > curr_qty:
                st.error("الكمية المتاحة لا تكفي للصرف.")
            else:
                new_qty = curr_qty - quantity if trans_type == "صرف" else curr_qty + quantity
                cursor.execute("""
                    INSERT INTO inventory (warehouse_id, item_id, quantity) VALUES (?, ?, ?)
                    ON CONFLICT(warehouse_id, item_id) DO UPDATE SET quantity = ?
                """, (wh_id, item_id, new_qty, new_qty))
                
                cursor.execute("""
                    INSERT INTO transactions (trans_date, trans_type, warehouse_id, item_id, partner_id, requester_name, quantity, unit_price, total_price, reference_no, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (trans_date, trans_type, wh_id, item_id, partner_id, requester_name, quantity, unit_price, total_price, reference_no, st.session_state['user_id']))
                
                # تسوية مالية بالخزنة
                if trans_type == "إضافة/توريد" and total_price > 0:
                    cursor.execute("INSERT INTO treasury_ledger (entry_date, warehouse_id, entry_type, partner_id, amount, statement, user_id) VALUES (?, ?, 'سداد توريد', ?, ?, ?, ?)",
                                   (trans_date, wh_id, partner_id, total_price, f"تكلفة توريد صنف إذن {reference_no}", st.session_state['user_id']))
                
                conn.commit()
                st.success(f"تم تسجيل الحركة بنجاح. الرصيد الحالي: {new_qty}")
    conn.close()

# ==========================================
# 10. التحويل بين المخازن
# ==========================================
elif choice == "🔄 التحويل بين المخازن":
    st.title("🔄 التحويل بين المخازن والتحويل الآلي")
    conn = get_connection()
    wh_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    items_df = pd.read_sql_query("SELECT id, code, name FROM items", conn)
    
    if len(wh_df) >= 2:
        with st.form("trf_f"):
            c1, c2, c3 = st.columns(3)
            trans_date = c1.date_input("التاريخ", value=datetime.date.today())
            from_wh = c2.selectbox("من مخزن (مورد)", wh_df['name'].tolist(), index=0)
            to_wh = c3.selectbox("إلى مخزن (عميل)", wh_df['name'].tolist(), index=1)
            
            item_disp = c1.selectbox("الصنف", items_df.apply(lambda r: f"{r['code']} - {r['name']}", axis=1).tolist())
            qty = c2.number_input("الكمية", min_value=1, value=1)
            req_person = c3.text_input("المسؤول عن النقل / المستلم")
            
            if st.form_submit_button("إجراء التحويل المخزني"):
                if from_wh == to_wh:
                    st.error("لا يمكن التحويل لنفس المخزن!")
                else:
                    from_id = wh_df[wh_df['name'] == from_wh]['id'].values[0]
                    to_id = wh_df[wh_df['name'] == to_wh]['id'].values[0]
                    item_id = items_df[items_df['code'] == item_disp.split(" - ")[0]]['id'].values[0]
                    
                    cursor = conn.cursor()
                    cursor.execute("SELECT quantity FROM inventory WHERE warehouse_id = ? AND item_id = ?", (from_id, item_id))
                    res_from = cursor.fetchone()
                    from_q = res_from['quantity'] if res_from else 0
                    
                    if qty > from_q:
                        st.error("الرصيد في المخزن المصدر غير كافٍ.")
                    else:
                        cursor.execute("UPDATE inventory SET quantity = quantity - ? WHERE warehouse_id = ? AND item_id = ?", (qty, from_id, item_id))
                        cursor.execute("""
                            INSERT INTO inventory (warehouse_id, item_id, quantity) VALUES (?, ?, ?)
                            ON CONFLICT(warehouse_id, item_id) DO UPDATE SET quantity = quantity + ?
                        """, (to_id, item_id, qty, qty))
                        
                        cursor.execute("""
                            INSERT INTO transactions (trans_date, trans_type, warehouse_id, dest_warehouse_id, item_id, requester_name, quantity, user_id)
                            VALUES (?, 'تحويل مخزني', ?, ?, ?, ?, ?, ?)
                        """, (trans_date, from_id, to_id, item_id, req_person, qty, st.session_state['user_id']))
                        
                        conn.commit()
                        st.success("تم التحويل المخزني بنجاح!")
    conn.close()

# ==========================================
# 11. إدارة المخازن والفروع
# ==========================================
elif choice == "🏭 إدارة المخازن والفروع":
    st.title("🏭 إدارة المخازن والفروع")
    conn = get_connection()
    c1, c2 = st.columns(2)
    with c1:
        with st.form("add_w"):
            wn = st.text_input("اسم المخزن/الفرع الجديد*")
            wl = st.text_input("العنوان")
            if st.form_submit_button("حفظ المخزن"):
                if wn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO warehouses (name, location) VALUES (?, ?)", (wn.strip(), wl.strip()))
                    conn.commit()
                    st.success("تم الحفظ بنجاح!")
                    st.rerun()
    with c2:
        st.dataframe(pd.read_sql_query("SELECT id, name AS 'المخزن', location AS 'الموقع' FROM warehouses", conn), use_container_width=True)
    conn.close()

# ==========================================
# 12. إصدار الفواتير A4
# ==========================================
elif choice == "🧾 إصدار فاتورة بيع A4":
    st.title("🧾 إصدار فاتورة بيع جديدة A4")
    conn = get_connection()
    cust_df = pd.read_sql_query("SELECT id, name FROM partners WHERE partner_type IN ('عميل', 'عميل ومورد')", conn)
    wh_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    items_df = pd.read_sql_query("SELECT id, code, name, selling_price FROM items", conn)
    
    if 'cart' not in st.session_state:
        st.session_state['cart'] = []
        
    c1, c2, c3 = st.columns(3)
    inv_date = c1.date_input("التاريخ", value=datetime.date.today())
    inv_num = c2.text_input("رقم الفاتورة", value=f"INV-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}")
    cust_opts = {r['name']: r['id'] for _, r in cust_df.iterrows()} if not cust_df.empty else {}
    sel_cust = c3.selectbox("العميل", list(cust_opts.keys())) if cust_opts else None
    
    wh_opts = {r['name']: r['id'] for _, r in wh_df.iterrows()}
    sel_wh = st.selectbox("المخزن المخصوم منه", list(wh_opts.keys()))
    sel_wh_id = wh_opts[sel_wh]
    
    st.markdown("---")
    st.subheader("🛒 إضافة بنود للفاتورة")
    col_a, col_b, col_c, col_d = st.columns([3, 1, 1, 1])
    item_list = items_df.apply(lambda r: f"{r['code']} - {r['name']}", axis=1).tolist() if not items_df.empty else []
    sel_item_str = col_a.selectbox("الصنف", item_list) if item_list else None
    
    if sel_item_str:
        item_code = sel_item_str.split(" - ")[0]
        item_row = items_df[items_df['code'] == item_code].iloc[0]
        
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM inventory WHERE warehouse_id = ? AND item_id = ?", (sel_wh_id, item_row['id']))
        res_q = cursor.fetchone()
        avail_q = res_q['quantity'] if res_q else 0
        
        st.info(f"الرصيد المتاح بالمخزن: **{avail_q}** قطعة")
        qty_in = col_b.number_input("الكمية", min_value=1, max_value=max(1, avail_q), value=1)
        price_in = col_c.number_input("سعر البيع", value=float(item_row['selling_price']))
        
        if col_d.button("➕ إضافة البند"):
            if avail_q < qty_in:
                st.error("الكمية المتاحة لا تكفي!")
            else:
                st.session_state['cart'].append({
                    'item_id': item_row['id'], 'code': item_row['code'], 'name': item_row['name'],
                    'qty': qty_in, 'price': price_in, 'total': qty_in * price_in
                })
                st.success("تمت الإضافة!")
                
    if st.session_state['cart']:
        df_cart = pd.DataFrame(st.session_state['cart'])
        st.dataframe(df_cart[['code', 'name', 'qty', 'price', 'total']], use_container_width=True)
        
        subtotal = df_cart['total'].sum()
        tax = subtotal * 0.14
        net_total = subtotal + tax
        st.write(f"**الصافي شامل الضريبة (14%):** {net_total:,.2f} ج.م")
        
        if st.button("💾 اعتـماد وتخزين الفاتورة"):
            partner_id = cust_opts[sel_cust]
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO invoices (invoice_number, invoice_date, partner_id, warehouse_id, sales_rep_id, total_amount, tax_amount, net_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (inv_num, inv_date, partner_id, sel_wh_id, st.session_state['user_id'], subtotal, tax, net_total))
            
            inv_id = cursor.lastrowid
            for line in st.session_state['cart']:
                cursor.execute("INSERT INTO invoice_items (invoice_id, item_id, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)",
                               (inv_id, line['item_id'], line['qty'], line['price'], line['total']))
                cursor.execute("UPDATE inventory SET quantity = quantity - ? WHERE warehouse_id = ? AND item_id = ?",
                               (line['qty'], sel_wh_id, line['item_id']))
                
            cursor.execute("""
                INSERT INTO treasury_ledger (entry_date, warehouse_id, entry_type, partner_id, amount, statement, user_id)
                VALUES (?, ?, 'مقبوضات مبيعات', ?, ?, ?, ?)
            """, (inv_date, sel_wh_id, partner_id, net_total, f"فاتورة مبيعات رقم {inv_num}", st.session_state['user_id']))
            
            conn.commit()
            st.success("تم إصدار وتسجيل الفاتورة والخزينة بنجاح!")
            st.session_state['cart'] = []
    conn.close()

# ==========================================
# 13. استعلام ومعاينة الفواتير
# ==========================================
elif choice == "🔍 استعلام وشاشة الفواتير":
    st.title("🔍 استعلام ومعاينة الفواتير الجاهزة للطباعة")
    conn = get_connection()
    inv_df = pd.read_sql_query("""
        SELECT inv.id, inv.invoice_number AS 'رقم الفاتورة', inv.invoice_date AS 'التاريخ', 
               p.name AS 'العميل', w.name AS 'المخزن', inv.net_amount AS 'الصافي'
        FROM invoices inv JOIN partners p ON inv.partner_id = p.id JOIN warehouses w ON inv.warehouse_id = w.id
        ORDER BY inv.id DESC
    """, conn)
    st.dataframe(inv_df, use_container_width=True)
    conn.close()

# ==========================================
# 14. المالية والحسابات وحركة الخزنة
# ==========================================
elif choice == "💰 حركة الخزنة والنثريات":
    st.title("💰 إدارة حركة الخزنة والنثريات")
    conn = get_connection()
    wh_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    
    if role == 'محاسب' and user_wh_id:
        wh_df = wh_df[wh_df['id'] == user_wh_id]
        
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("➕ إذن قيد حركة مالية / نثريات")
        with st.form("treasury_form", clear_on_submit=True):
            entry_date = st.date_input("التاريخ", value=datetime.date.today())
            wh_name = st.selectbox("المخزن/الفرع", wh_df['name'].tolist())
            entry_type = st.selectbox("نوع الحركة المالية", ["مصروفات/نثريات", "مقبوضات مبيعات", "إيداع/سحب"])
            amount = st.number_input("المبلغ (ج.م)*", min_value=0.1, value=100.0)
            statement = st.text_input("البيان / الشرح*", placeholder="مثل: فاتورة كهرباء / مصاريف شحن")
            
            if st.form_submit_button("تسجيل الحركة المالية"):
                wh_id = wh_df[wh_df['name'] == wh_name]['id'].values[0]
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO treasury_ledger (entry_date, warehouse_id, entry_type, amount, statement, user_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (entry_date, wh_id, entry_type, amount, statement, st.session_state['user_id']))
                conn.commit()
                st.success("تم تسجيل الحركة المالية بنجاح!")
                
    with c2:
        st.subheader("📊 رصيد الخزنة الحالية")
        selected_wh = st.selectbox("اختر الفرع لرؤية الخزنة:", wh_df['name'].tolist())
        sel_wh_id = wh_df[wh_df['name'] == selected_wh]['id'].values[0]
        
        t_df = pd.read_sql_query("SELECT entry_type, amount FROM treasury_ledger WHERE warehouse_id = ?", conn, params=(sel_wh_id,))
        inc = t_df[t_df['entry_type'].isin(['مقبوضات مبيعات', 'إيداع/سحب'])]['amount'].sum()
        exp = t_df[t_df['entry_type'].isin(['مصروفات/نثريات', 'سداد توريد'])]['amount'].sum()
        balance = inc - exp
        
        st.metric("إجمالي المقبوضات/الوارد", f"{inc:,.2f} ج.م")
        st.metric("إجمالي المصروفات/المنصرف", f"{exp:,.2f} ج.م")
        st.metric("صافي رصيد الخزنة الحالية", f"{balance:,.2f} ج.م")
        
    st.markdown("---")
    st.subheader("📜 دفتر الخزنة التفصيلي")
    ledger_df = pd.read_sql_query("""
        SELECT t.entry_date AS 'التاريخ', w.name AS 'الفرع', t.entry_type AS 'نوع الحركة',
               t.amount AS 'المبلغ', t.statement AS 'البيان', u.full_name AS 'المسؤول'
        FROM treasury_ledger t JOIN warehouses w ON t.warehouse_id = w.id JOIN users u ON t.user_id = u.id
        ORDER BY t.id DESC
    """, conn)
    st.dataframe(ledger_df, use_container_width=True)
    conn.close()

# ==========================================
# 15. تقرير الأرباح والخسائر وكشوف الحساب
# ==========================================
elif choice == "📈 تقرير الأرباح والخسائر وكشف الحساب":
    st.title("📈 تقرير الأرباح والخسائر الحسابي")
    conn = get_connection()
    c1, c2 = st.columns(2)
    s_d = c1.date_input("من تاريخ", value=datetime.date.today() - datetime.timedelta(days=30))
    e_d = c2.date_input("إلى تاريخ", value=datetime.date.today())
    
    sales = pd.read_sql_query("SELECT SUM(net_amount) AS total FROM invoices WHERE invoice_date BETWEEN ? AND ?", conn, params=(s_d, e_d)).iloc[0]['total'] or 0.0
    purchases = pd.read_sql_query("SELECT SUM(total_price) AS total FROM transactions WHERE trans_type = 'إضافة/توريد' AND trans_date BETWEEN ? AND ?", conn, params=(s_d, e_d)).iloc[0]['total'] or 0.0
    expenses = pd.read_sql_query("SELECT SUM(amount) AS total FROM treasury_ledger WHERE entry_type = 'مصروفات/نثريات' AND entry_date BETWEEN ? AND ?", conn, params=(s_d, e_d)).iloc[0]['total'] or 0.0
    
    gross_profit = sales - purchases
    net_profit = gross_profit - expenses
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("إجمالي الفواتير/المبيعات", f"{sales:,.2f} ج.م")
    col2.metric("تكلفة التوريدات/المشتريات", f"{purchases:,.2f} ج.م")
    col3.metric("النثريات والمصروفات", f"{expenses:,.2f} ج.م")
    col4.metric("صافي الربح النهائي", f"{net_profit:,.2f} ج.م", delta=f"{net_profit:,.2f}")
    
    conn.close()

# ==========================================
# 16. التقارير التشغيلية والرسوم البيانية
# ==========================================
elif choice == "📜 التقارير التشغيلية والاستعلامات":
    st.title("📜 التقارير التشغيلية وتصدير البيانات")
    conn = get_connection()
    
    show_charts = st.checkbox("📈 إظهار الرسوم البيانية التفاعلية (Charts & Graphs)")
    
    df_res = pd.read_sql_query("""
        SELECT t.trans_date AS 'التاريخ', t.trans_type AS 'نوع الحركة', w.name AS 'المخزن',
               i.name AS 'الصنف', t.quantity AS 'الكمية', t.total_price AS 'الإجمالي', t.requester_name AS 'المسؤول'
        FROM transactions t 
        JOIN warehouses w ON t.warehouse_id = w.id 
        JOIN items i ON t.item_id = i.id 
        ORDER BY t.id DESC
    """, conn)
    
    if show_charts and not df_res.empty:
        fig = px.bar(df_res, x='نوع الحركة', y='الإجمالي', color='المخزن', barmode='group', title="توزيع قيم الحركات حسب نوع الإذن والمخزن")
        st.plotly_chart(fig, use_container_width=True)
        
    st.dataframe(df_res, use_container_width=True)
    
    # تصدير Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df_res.to_excel(w, index=False)
    st.download_button("📥 تصدير لملف Excel (.xlsx)", buf.getvalue(), "AlMohaseb_Report.xlsx")
    conn.close()

# ==========================================
# 17. تقارير الإدارة الاستراتيجية
# ==========================================
elif choice == "👑 تقارير الإدارة الاستراتيجية":
    st.title("👑 تقارير وتحليلات الإدارة العليا")
    conn = get_connection()
    st.subheader("🥇 الأكثر مبيعاً والأعلى سحباً للعملاء")
    df_top = pd.read_sql_query("""
        SELECT i.name AS 'الصنف', SUM(ii.quantity) AS 'إجمالي الكميات المباعة', SUM(ii.total_price) AS 'إجمالي الإيراد'
        FROM invoice_items ii JOIN items i ON ii.item_id = i.id GROUP BY i.id ORDER BY SUM(ii.total_price) DESC
    """, conn)
    st.dataframe(df_top, use_container_width=True)
    conn.close()

# ==========================================
# 18. إدارة المستخدمين وتغيير كلمات السر
# ==========================================
elif choice == "⚙️ إدارة المستخدمين والصلاحيات":
    st.title("⚙️ إدارة المستخدمين والصلاحيات")
    conn = get_connection()
    
    wh_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    wh_opts = {r['name']: r['id'] for _, r in wh_df.iterrows()}
    
    with st.form("add_user_form", clear_on_submit=True):
        u_name = st.text_input("اسم المستخدم (Username)*")
        f_name = st.text_input("الاسم الكامل*")
        p_word = st.text_input("كلمة السر*", type="password")
        u_role = st.selectbox("الصلاحية*", ["مسؤول مخازن", "ممثل مبيعات", "محاسب", "مدير النظام"])
        assigned_wh = st.selectbox("المخزن/الفرع المخصص", list(wh_opts.keys()))
        
        if st.form_submit_button("إضافة المستخدم"):
            if u_name and p_word:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO users (username, password, full_name, role, assigned_warehouse_id)
                        VALUES (?, ?, ?, ?, ?)
                    """, (u_name.strip(), hash_password(p_word), f_name.strip(), u_role, wh_opts[assigned_wh]))
                    conn.commit()
                    st.success("تم التكويد بنجاح!")
                except:
                    st.error("اسم المستخدم مكرر.")
                    
    st.dataframe(pd.read_sql_query("SELECT id, username, full_name, role, assigned_warehouse_id FROM users", conn), use_container_width=True)
    conn.close()

# ==========================================
# 19. النسخ الاحتياطي والاستعادة (Backup & Restore)
# ==========================================
elif choice == "💾 النسخ الاحتياطي والاستعادة":
    st.title("💾 النسخ الاحتياطي واستعادة البيانات (Backup & Restore)")
    st.info("تتيح لك هذه الشاشة أخذ نسخة احتياطية كاملة من البيانات واستعادتها بأمان في أي وقت.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📥 تحميل نسخة احتياطية (Download Backup)")
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "rb") as f:
                db_bytes = f.read()
            st.download_button(
                label="💾 تحميل قاعدة البيانات الحالية (.db)",
                data=db_bytes,
                file_name=f"AlMohaseb_Backup_{datetime.date.today()}.db",
                mime="application/x-sqlite3"
            )
            
    with col2:
        st.subheader("📤 استعادة نسخة احتياطية (Restore Database)")
        uploaded_file = st.file_uploader("اختر ملف قاعدة البيانات لاستعادتها (.db)", type=["db"])
        if uploaded_file is not None:
            if st.button("⚠️ تأكيد استعادة النسخة الاحتياطية"):
                with open(DB_FILE, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success("✅ تم استعادة قاعدة البيانات بنجاح! سيتم إعادة تحميل النظام...")
                st.rerun()