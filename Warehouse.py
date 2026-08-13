import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib
import io

# ==========================================
# 1. تهيئة الصفحة والهوية البصرية Towertech
# ==========================================
st.set_page_config(
    page_title="Towertech - ERP Warehouse & Invoicing System",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# تنسيق الجداول والـ Header والـ CSS وطباعة الفاتورة A4
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: RTL;
        text-align: right;
    }
    
    .brand-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 2px solid #38bdf8;
        color: #ffffff;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(56, 189, 248, 0.25);
    }
    .brand-logo {
        font-size: 28px;
        font-weight: 800;
        color: #38bdf8;
        letter-spacing: 1.5px;
    }
    .brand-subtitle {
        font-size: 14px;
        color: #94a3b8;
    }

    /* تنسيق طباعة الفاتورة A4 */
    @media print {
        body * { visibility: hidden; }
        .printable-invoice, .printable-invoice * { visibility: visible; }
        .printable-invoice {
            position: absolute; left: 0; top: 0; width: 100%;
            margin: 0; padding: 20px; font-size: 14px; color: #000; background: #fff;
        }
        .no-print { display: none !important; }
    }
    
    .invoice-box {
        background-color: #ffffff; color: #000000; padding: 30px;
        border: 1px solid #e2e8f0; border-radius: 10px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05); margin-top: 15px;
    }
    .invoice-header {
        border-bottom: 2px solid #0284c7; padding-bottom: 15px; margin-bottom: 20px;
    }
    .invoice-title { font-size: 26px; font-weight: bold; color: #0284c7; }
    
    .stButton>button {
        width: 100%; background-color: #0284c7; color: white;
        font-weight: 700; border-radius: 8px; border: none; padding: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. إدارة قاعدة البيانات SQLite (دائمة)
# ==========================================
DB_FILE = "towertech_v3.db"

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول المخازن
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warehouses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            location TEXT,
            is_main INTEGER DEFAULT 0
        )
    ''')
    
    # جدول شركاء الأعمال (عملاء، موردين، عميل ومورد، ومخازن كشركاء)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS partners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            phone TEXT,
            partner_type TEXT NOT NULL, -- 'عميل', 'مورد', 'عميل ومورد', 'مخزن كشريك'
            address TEXT,
            linked_warehouse_id INTEGER DEFAULT NULL,
            notes TEXT,
            FOREIGN KEY (linked_warehouse_id) REFERENCES warehouses(id)
        )
    ''')
    
    # جدول الأصناف التفصيلي
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
    
    # جدول رصيد المخزون في كل مخزن
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
            trans_type TEXT NOT NULL, -- 'إضافة/توريد', 'صرف', 'مرتجع', 'تحويل مخزني'
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (dest_warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (item_id) REFERENCES items(id),
            FOREIGN KEY (partner_id) REFERENCES partners(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (partner_id) REFERENCES partners(id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (sales_rep_id) REFERENCES users(id)
        )
    ''')
    
    # جدول بنود الفواتير
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        )
    ''')
    
    # إنشاء أدمن وافتراضيات النظام
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
            ('admin', hash_password('admin123'), 'مدير النظام الرئيسي', 'مدير النظام')
        )
        
    cursor.execute("SELECT * FROM warehouses WHERE is_main = 1")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO warehouses (name, location, is_main) VALUES (?, ?, ?)",
            ('المخزن الرئيسي (HQ)', 'فرع المركز الرئيسي - القاهرة', 1)
        )
        main_wh_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO partners (name, partner_type, linked_warehouse_id, notes) VALUES (?, ?, ?, ?)",
            ('المخزن الرئيسي (HQ)', 'مخزن كشريك', main_wh_id, 'مخزن معتمد للتحويلات المخزنية')
        )
        
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 3. الهيدر والشعار
# ==========================================
def render_brand_header():
    st.markdown("""
        <div class="brand-header">
            <div class="brand-logo">💻 TOWERTECH IT & SYSTEMS ⚡</div>
            <div class="brand-subtitle">نظام إدارة المخازن، التحويلات، والفواتير الذكية</div>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# 4. إدارة جلسة المستخدم وتسجيل الدخول
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

def login_screen():
    render_brand_header()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔑 تسجيل الدخول للتطبيق")
        username_input = st.text_input("اسم المستخدم")
        password_input = st.text_input("كلمة السر", type="password")
        
        if st.button("دخول"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, full_name, role FROM users WHERE username = ? AND password = ?",
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
                st.success(f"مرحباً بك، {user['full_name']} [{user['role']}]")
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة السر غير صحيحة")

if not st.session_state['logged_in']:
    login_screen()
    st.stop()

# ==========================================
# 5. القائمة الجانبية والصلاحيات
# ==========================================
role = st.session_state['user_role']

with st.sidebar:
    st.markdown("### 🏢 Towertech Systems")
    st.write(f"👤 **المستخدم:** {st.session_state['full_name']}")
    st.write(f"💼 **الصلاحية:** `{role}`")
    st.markdown("---")
    
    menu_options = ["📊 المخزون والتنبيهات الحالية"]
    
    if role in ['مدير النظام', 'مسؤول مخازن']:
        menu_options.append("🏷️ إضافة وتكويد أصناف جديدة")
        menu_options.append("🤝 تكويد العملاء والموردين والمخازن كشركاء")
        menu_options.append("📝 تسجيل حركة مخزنية (إضافة / صرف / مرتجع)")
        menu_options.append("🔄 التحويل بين المخازن (صرف وإضافة تلقائية)")
        menu_options.append("🏭 إدارة المخازن الفرعية والرئيسية")
        
    if role in ['مدير النظام', 'ممثل مبيعات']:
        menu_options.append("🧾 إصدار فاتورة بيع جديدة (A4)")
        
    menu_options.append("🔍 شاشة استعلام واستعراض الفواتير")
    menu_options.append("📜 التقارير الاستعلامية والتشغيلية")
    menu_options.append("👑 تقارير الإدارة الاستراتيجية والاحصائيات")
    
    if role == 'مدير النظام':
        menu_options.append("⚙️ إدارة المستخدمين وتغيير كلمات السر")
        
    choice = st.radio("انتقل إلى الشاشة:", menu_options)
    st.markdown("---")
    if st.button("🚪 تسجيل الخروج"):
        st.session_state['logged_in'] = False
        st.rerun()

render_brand_header()

# ==========================================
# 6. شاشة (1): المخزون والتنبيهات الحالية
# ==========================================
if choice == "📊 المخزون والتنبيهات الحالية":
    st.title("📊 موقف المخزون والجرد الحالي")
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
            i.unit AS 'الوحدة', COALESCE(inv.quantity, 0) AS 'الكمية المتاحة',
            i.min_quantity AS 'الحد الأدنى', i.selling_price AS 'سعر البيع الافتراضي',
            p.name AS 'المورد الرئيسي'
        FROM items i
        CROSS JOIN warehouses w
        LEFT JOIN inventory inv ON inv.item_id = i.id AND inv.warehouse_id = w.id
        LEFT JOIN partners p ON i.main_supplier_id = p.id
    """
    if sel_wh_id:
        query += f" WHERE w.id = {sel_wh_id}"
        
    df_stock = pd.read_sql_query(query, conn)
    low_stock = df_stock[df_stock['الكمية المتاحة'] <= df_stock['الحد الأدنى']]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("إجمالي الأصناف المسجلة", len(df_stock['الكود'].unique()))
    c2.metric("إجمالي عدد القطع بالمخزن", int(df_stock['الكمية المتاحة'].sum()))
    c3.metric("أصناف وصلت للحد الأدنى فأقل", len(low_stock), delta_color="inverse")
    
    st.markdown("---")
    if not low_stock.empty:
        st.warning(f"⚠️ **تنبيه عاجل:** هناك ({len(low_stock)}) أصناف بلغت الحد الأدنى المطلوب للتوريد!")
        with st.expander("🚨 عرض قائمة الأصناف المنخفضة"):
            st.dataframe(low_stock, use_container_width=True)
            
    st.subheader("📋 قائمة الأصناف والجرد التفصيلي")
    search_q = st.text_input("🔍 بحث (اسم، كود، Part Number، أو Serial):")
    if search_q:
        df_stock = df_stock[
            df_stock['اسم الصنف'].astype(str).str.contains(search_q, case=False) |
            df_stock['الكود'].astype(str).str.contains(search_q, case=False) |
            df_stock['Part Number'].astype(str).str.contains(search_q, case=False) |
            df_stock['S/N'].astype(str).str.contains(search_q, case=False)
        ]
    st.dataframe(df_stock, use_container_width=True)
    conn.close()

# ==========================================
# 7. شاشة (2): تكويد أصناف جديدة
# ==========================================
elif choice == "🏷️ إضافة وتكويد أصناف جديدة":
    st.title("🏷️ إضافة وتكويد صنف جديد بالكامل")
    conn = get_connection()
    suppliers_df = pd.read_sql_query("SELECT id, name FROM partners WHERE partner_type IN ('مورد', 'عميل ومورد')", conn)
    
    with st.form("add_item_f", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            item_code = st.text_input("كود الصنف (فريد)*", placeholder="CPU-INTEL-13700K")
            part_number = st.text_input("Part Number", placeholder="BX8071513700K")
            serial_number = st.text_input("Serial Number (S/N)", placeholder="SN-98234729")
        with c2:
            item_name = st.text_input("اسم الصنف الكامل*", placeholder="معالج Intel Core i7 13700K")
            category = st.selectbox("التصنيف", ["معالجات", "كروت شاشة", "شبكات وسيرفرات", "شاشات", "مغذيات طاقة", "أخرى"])
            unit = st.selectbox("الوحدة", ["قطعة", "متر", "طقم", "جهاز", "كرتونة"])
        with c3:
            min_qty = st.number_input("الحد الأدنى للتنبيه*", min_value=0, value=3)
            cost_price = st.number_input("سعر التكلفة (ج.م)", min_value=0.0, value=0.0, step=100.0)
            selling_price = st.number_input("سعر البيع المقترح (ج.م)*", min_value=0.0, value=0.0, step=100.0)
            
        sup_opts = {"غير محدد": None}
        for _, r in suppliers_df.iterrows():
            sup_opts[r['name']] = r['id']
        main_sup = st.selectbox("المورد الرئيسي المفضل", list(sup_opts.keys()))
        image_url = st.text_input("رابط صورة الصنف (URL اختياري)")
        notes = st.text_area("تفاصيل ومواصفات إضافية")
        
        if st.form_submit_button("💾 حفظ البيانات"):
            if not item_code or not item_name:
                st.error("يرجى إدخال البيانات الإلزامية (*)")
            else:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO items (code, part_number, serial_number, name, category, unit, main_supplier_id, min_quantity, cost_price, selling_price, image_url, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (item_code.strip(), part_number.strip(), serial_number.strip(), item_name.strip(), category, unit, sup_opts[main_sup], min_qty, cost_price, selling_price, image_url.strip(), notes))
                    conn.commit()
                    st.success(f"تم حفظ الصنف ({item_name}) بنجاح!")
                except sqlite3.IntegrityError:
                    st.error("كود الصنف مستخدم ومسجل مسبقاً.")
    conn.close()

# ==========================================
# 8. شاشة (3): تكويد العملاء والموردين والمخازن كشركاء
# ==========================================
elif choice == "🤝 تكويد العملاء والموردين والمخازن كشركاء":
    st.title("🤝 إدارة وتكويد شركاء الأعمال")
    conn = get_connection()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("➕ إضافة جهة / شريك أعمال")
        with st.form("add_p_form", clear_on_submit=True):
            p_name = st.text_input("اسم الجهة / الشركة / الشريك*")
            p_type = st.selectbox("نوع التعامل*", ["عميل", "مورد", "عميل ومورد (مزدوج)", "مخزن كشريك (للتحويلات)"])
            p_phone = st.text_input("الهاتف")
            p_address = st.text_input("العنوان")
            p_notes = st.text_area("ملاحظات")
            
            if st.form_submit_button("حفظ الشريك"):
                if p_name:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO partners (name, partner_type, phone, address, notes) VALUES (?, ?, ?, ?, ?)",
                                       (p_name.strip(), p_type, p_phone.strip(), p_address.strip(), p_notes))
                        conn.commit()
                        st.success("تم الحفظ بنجاح!")
                        st.rerun()
                    except:
                        st.error("الاسم موجود بالفعل.")
    with c2:
        st.subheader("📋 قائمة شركاء الأعمال")
        st.dataframe(pd.read_sql_query("SELECT id, name AS 'الاسم', partner_type AS 'التصنيف', phone AS 'الهاتف' FROM partners", conn), use_container_width=True)
    conn.close()

# ==========================================
# 9. شاشة (4): تسجيل حركة مخزنية
# ==========================================
elif choice == "📝 تسجيل حركة مخزنية (إضافة / صرف / مرتجع)":
    st.title("📝 تسجيل أذون الحركة المخزنية")
    conn = get_connection()
    wh_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    items_df = pd.read_sql_query("SELECT id, code, name FROM items", conn)
    partners_df = pd.read_sql_query("SELECT id, name, partner_type FROM partners", conn)
    
    with st.form("trans_f", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            trans_date = st.date_input("تاريخ الحركة*", value=datetime.date.today())
            trans_type = st.selectbox("نوع الحركة*", ["إضافة/توريد", "صرف", "مرتجع"])
            wh_name = st.selectbox("المخزن المعني*", wh_df['name'].tolist())
        with c2:
            item_disp = st.selectbox("الصنف*", items_df.apply(lambda r: f"{r['code']} - {r['name']}", axis=1).tolist())
            partner_opts = ["عام / جهة غير محددة"] + partners_df.apply(lambda r: f"{r['id']} - {r['name']} ({r['partner_type']})", axis=1).tolist()
            selected_p = st.selectbox("الجهة (عميل/مورد/مخزن شريك)*", partner_opts)
            requester_name = st.text_input("اسم المسؤول عن طلب الصرف / المستلم*", placeholder="اسم المهندس / المستلم")
        with c3:
            quantity = st.number_input("الكمية*", min_value=1, value=1)
            unit_price = st.number_input("سعر الوحدة (ج.م)*", min_value=0.0, value=0.0, step=50.0)
            reference_no = st.text_input("رقم المرجع / الإذن", placeholder="REF-2026-100")
            
        trans_notes = st.text_input("ملاحظات إضافية")
        
        if st.form_submit_button("🚀 اعتـماد الحركة"):
            item_id = items_df[items_df['code'] == item_disp.split(" - ")[0]]['id'].values[0]
            wh_id = wh_df[wh_df['name'] == wh_name]['id'].values[0]
            partner_id = int(selected_p.split(" - ")[0]) if selected_p != "عام / جهة غير محددة" else None
            total_price = quantity * unit_price
            
            cursor = conn.cursor()
            cursor.execute("SELECT quantity FROM inventory WHERE warehouse_id = ? AND item_id = ?", (wh_id, item_id))
            res = cursor.fetchone()
            curr_qty = res['quantity'] if res else 0
            
            if trans_type == "صرف" and quantity > curr_qty:
                st.error(f"❌ الرصيد المتاح ({curr_qty}) أقل من الكمية المطلوبة ({quantity}).")
            else:
                new_qty = curr_qty - quantity if trans_type == "صرف" else curr_qty + quantity
                
                cursor.execute("""
                    INSERT INTO inventory (warehouse_id, item_id, quantity)
                    VALUES (?, ?, ?)
                    ON CONFLICT(warehouse_id, item_id) DO UPDATE SET quantity = ?
                """, (wh_id, item_id, new_qty, new_qty))
                
                cursor.execute("""
                    INSERT INTO transactions 
                    (trans_date, trans_type, warehouse_id, item_id, partner_id, requester_name, quantity, unit_price, total_price, reference_no, notes, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (trans_date, trans_type, wh_id, item_id, partner_id, requester_name, quantity, unit_price, total_price, reference_no, trans_notes, st.session_state['user_id']))
                
                conn.commit()
                st.success(f"✅ تم تنفيذ حركة ({trans_type}) بنجاح. الرصيد الجديد بالمخزن: {new_qty}")
    conn.close()

# ==========================================
# 10. شاشة (5): التحويل الآلي بين المخازن
# ==========================================
elif choice == "🔄 التحويل بين المخازن (صرف وإضافة تلقائية)":
    st.title("🔄 التحويل بين المخازن (من المخزن الرئيسي إلى المخازن الفرعية والعكس)")
    conn = get_connection()
    wh_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    items_df = pd.read_sql_query("SELECT id, code, name FROM items", conn)
    
    if len(wh_df) < 2:
        st.warning("⚠️ ينبغي وجود مخزنين على الأقل لإجراء تحويلات بين المخازن.")
    else:
        with st.form("transfer_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            trans_date = c1.date_input("تاريخ التحويل*", value=datetime.date.today())
            from_wh_name = c2.selectbox("من المخزن (المحَوِّل / المورد)*", wh_df['name'].tolist(), index=0)
            to_wh_name = c3.selectbox("إلى المخزن (المحَوَّل إليه / العميل)*", wh_df['name'].tolist(), index=1 if len(wh_df) > 1 else 0)
            
            col_a, col_b, col_c = st.columns(3)
            item_disp = col_a.selectbox("اختر الصنف المراد تحويله*", items_df.apply(lambda r: f"{r['code']} - {r['name']}", axis=1).tolist())
            transfer_qty = col_b.number_input("الكمية المحولة*", min_value=1, value=1)
            requester_name = col_c.text_input("اسم المسلم / المسؤول عن النقل*", placeholder="اسم السائق أو مندوب النقل")
            
            ref_no = st.text_input("رقم إذن التحويل", placeholder="TRF-2026-001")
            transfer_notes = st.text_input("ملاحظات أسباب التحويل")
            
            if st.form_submit_button("🔁 تنفيذ التحويل المخزني الفوري"):
                if from_wh_name == to_wh_name:
                    st.error("❌ لا يمكن التحويل لنفس المخزن!")
                else:
                    from_wh_id = wh_df[wh_df['name'] == from_wh_name]['id'].values[0]
                    to_wh_id = wh_df[wh_df['name'] == to_wh_name]['id'].values[0]
                    item_id = items_df[items_df['code'] == item_disp.split(" - ")[0]]['id'].values[0]
                    
                    cursor = conn.cursor()
                    cursor.execute("SELECT quantity FROM inventory WHERE warehouse_id = ? AND item_id = ?", (from_wh_id, item_id))
                    res_from = cursor.fetchone()
                    from_curr_qty = res_from['quantity'] if res_from else 0
                    
                    if transfer_qty > from_curr_qty:
                        st.error(f"❌ الرصيد المتاح بالمخزن المصدر ({from_wh_name}) هو ({from_curr_qty}) فقط، ولا يكفي للتحويل.")
                    else:
                        # 1. خصم من المخزن المصدر
                        new_from_qty = from_curr_qty - transfer_qty
                        cursor.execute("UPDATE inventory SET quantity = ? WHERE warehouse_id = ? AND item_id = ?", (new_from_qty, from_wh_id, item_id))
                        cursor.execute("""
                            INSERT INTO transactions (trans_date, trans_type, warehouse_id, dest_warehouse_id, item_id, requester_name, quantity, reference_no, notes, user_id)
                            VALUES (?, 'صرف تحويل مخزني', ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (trans_date, from_wh_id, to_wh_id, item_id, requester_name, transfer_qty, ref_no, f"تحويل إلى {to_wh_name}: {transfer_notes}", st.session_state['user_id']))
                        
                        # 2. إضافة للمخزن المستقبل
                        cursor.execute("SELECT quantity FROM inventory WHERE warehouse_id = ? AND item_id = ?", (to_wh_id, item_id))
                        res_to = cursor.fetchone()
                        to_curr_qty = res_to['quantity'] if res_to else 0
                        new_to_qty = to_curr_qty + transfer_qty
                        
                        cursor.execute("""
                            INSERT INTO inventory (warehouse_id, item_id, quantity)
                            VALUES (?, ?, ?)
                            ON CONFLICT(warehouse_id, item_id) DO UPDATE SET quantity = ?
                        """, (to_wh_id, item_id, new_to_qty, new_to_qty))
                        
                        cursor.execute("""
                            INSERT INTO transactions (trans_date, trans_type, warehouse_id, dest_warehouse_id, item_id, requester_name, quantity, reference_no, notes, user_id)
                            VALUES (?, 'إضافة تحويل مخزني', ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (trans_date, to_wh_id, from_wh_id, item_id, requester_name, transfer_qty, ref_no, f"تحويل قادم من {from_wh_name}: {transfer_notes}", st.session_state['user_id']))
                        
                        conn.commit()
                        st.success(f"✅ تم التحويل بنجاح من ({from_wh_name}) إلى ({to_wh_name})!")
    conn.close()

# ==========================================
# 11. شاشة (6): إدارة المخازن الفرعية
# ==========================================
elif choice == "🏭 إدارة المخازن الفرعية والرئيسية":
    st.title("🏭 إدارة وتكويد المخازن")
    conn = get_connection()
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("إضافة مخزن جديد")
        with st.form("add_w_f"):
            wn = st.text_input("اسم المخزن*")
            wl = st.text_input("الموقع الجغرافي")
            if st.form_submit_button("حفظ المخزن"):
                if wn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO warehouses (name, location, is_main) VALUES (?, ?, 0)", (wn.strip(), wl.strip()))
                        wh_id = cursor.lastrowid
                        cursor.execute("INSERT INTO partners (name, partner_type, linked_warehouse_id) VALUES (?, 'مخزن كشريك', ?)", (wn.strip(), wh_id))
                        conn.commit()
                        st.success("تم التكويد بنجاح!")
                        st.rerun()
                    except:
                        st.error("الاسم مكرر.")
    with c2:
        st.dataframe(pd.read_sql_query("SELECT id, name AS 'المخزن', location AS 'الموقع' FROM warehouses", conn), use_container_width=True)
    conn.close()

# ==========================================
# 12. شاشة (7): إصدار الفواتير A4
# ==========================================
elif choice == "🧾 إصدار فاتورة بيع جديدة (A4)":
    st.title("🧾 إصدار فاتورة بيع جديدة مقاس A4")
    conn = get_connection()
    customers_df = pd.read_sql_query("SELECT id, name FROM partners WHERE partner_type IN ('عميل', 'عميل ومورد')", conn)
    warehouses_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    items_df = pd.read_sql_query("SELECT id, code, name, selling_price FROM items", conn)
    
    if customers_df.empty or items_df.empty:
        st.warning("⚠️ يجب تكويد عملاء وأصناف أولاً لإصدار الفواتير.")
    else:
        if 'cart' not in st.session_state:
            st.session_state['cart'] = []
            
        c1, c2, c3 = st.columns(3)
        inv_date = c1.date_input("تاريخ الفاتورة*", value=datetime.date.today())
        inv_num = c2.text_input("رقم الفاتورة*", value=f"INV-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}")
        cust_opts = {r['name']: r['id'] for _, r in customers_df.iterrows()}
        selected_cust_name = c3.selectbox("العميل*", list(cust_opts.keys()))
        
        wh_opts = {r['name']: r['id'] for _, r in warehouses_df.iterrows()}
        selected_wh_name = st.selectbox("خصم من مخزن*", list(wh_opts.keys()))
        selected_wh_id = wh_opts[selected_wh_name]
        
        st.markdown("---")
        st.subheader("🛒 إضافة بنود إلى الفاتورة")
        col_a, col_b, col_c, col_d = st.columns([3, 1, 1, 1])
        item_disp_list = items_df.apply(lambda r: f"{r['code']} - {r['name']}", axis=1).tolist()
        sel_item_str = col_a.selectbox("اختر الصنف", item_disp_list)
        
        item_code = sel_item_str.split(" - ")[0]
        selected_item_row = items_df[items_df['code'] == item_code].iloc[0]
        
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM inventory WHERE warehouse_id = ? AND item_id = ?", (selected_wh_id, selected_item_row['id']))
        res_stock = cursor.fetchone()
        avail_stock = res_stock['quantity'] if res_stock else 0
        
        st.info(f"💡 الرصيد المتاح لهذا الصنف في ({selected_wh_name}) هو: **{avail_stock}** قطعة")
        
        qty_input = col_b.number_input("الكمية", min_value=1, max_value=max(1, avail_stock), value=1)
        price_input = col_c.number_input("سعر البيع للقطعة", min_value=0.0, value=float(selected_item_row['selling_price']), step=50.0)
        
        if col_d.button("➕ إضافة للبند"):
            if avail_stock < qty_input:
                st.error("الكمية المطلوبة أكبر من الرصيد المتاح بالمخزن!")
            else:
                st.session_state['cart'].append({
                    'item_id': selected_item_row['id'],
                    'code': selected_item_row['code'],
                    'name': selected_item_row['name'],
                    'qty': qty_input,
                    'price': price_input,
                    'total': qty_input * price_input
                })
                st.success("تمت إضافة البند إلى سلة الفاتورة!")
                
        if st.session_state['cart']:
            st.markdown("### 📋 بنود الفاتورة الحالية:")
            df_cart = pd.DataFrame(st.session_state['cart'])
            st.dataframe(df_cart[['code', 'name', 'qty', 'price', 'total']], use_container_width=True)
            
            subtotal = df_cart['total'].sum()
            tax = subtotal * 0.14
            net_total = subtotal + tax
            
            st.write(f"**الإجمالي قبل الضريبة:** {subtotal:,.2f} ج.م | **ضريبة القيمة المضافة (14%):** {tax:,.2f} ج.م | **الصافي النهائي:** {net_total:,.2f} ج.م")
            
            if st.button("🗑️ مسح محتويات الفاتورة"):
                st.session_state['cart'] = []
                st.rerun()
                
            inv_notes = st.text_input("ملاحظات وشروط الفاتورة")
            
            if st.button("💾 حفظ الفاتورة وطباعتها"):
                customer_id = cust_opts[selected_cust_name]
                cursor.execute("""
                    INSERT INTO invoices (invoice_number, invoice_date, partner_id, warehouse_id, sales_rep_id, total_amount, tax_amount, net_amount, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (inv_num, inv_date, customer_id, selected_wh_id, st.session_state['user_id'], subtotal, tax, net_total, inv_notes))
                
                invoice_id = cursor.lastrowid
                for line in st.session_state['cart']:
                    cursor.execute("""
                        INSERT INTO invoice_items (invoice_id, item_id, quantity, unit_price, total_price)
                        VALUES (?, ?, ?, ?, ?)
                    """, (invoice_id, line['item_id'], line['qty'], line['price'], line['total']))
                    
                    # خصم المخزون
                    cursor.execute("SELECT quantity FROM inventory WHERE warehouse_id = ? AND item_id = ?", (selected_wh_id, line['item_id']))
                    curr_q = cursor.fetchone()['quantity']
                    new_q = curr_q - line['qty']
                    cursor.execute("UPDATE inventory SET quantity = ? WHERE warehouse_id = ? AND item_id = ?", (new_q, selected_wh_id, line['item_id']))
                    
                    # تسجيل حركة صرف متسقة
                    cursor.execute("""
                        INSERT INTO transactions (trans_date, trans_type, warehouse_id, item_id, partner_id, requester_name, quantity, unit_price, total_price, reference_no, notes, user_id)
                        VALUES (?, 'صرف', ?, ?, ?, ?, ?, ?, ?, ?, 'صرف تلقائي بموجب فاتورة مبيعات', ?)
                    """, (inv_date, selected_wh_id, line['item_id'], customer_id, st.session_state['full_name'], line['qty'], line['price'], line['total'], inv_num, st.session_state['user_id']))
                    
                conn.commit()
                st.success(f"✅ تم إصدار وحفظ الفاتورة رقم ({inv_num}) بنجاح!")
                st.session_state['cart'] = []
    conn.close()

# ==========================================
# 13. شاشة (8): استعلام ومعاينة الفواتير
# ==========================================
elif choice == "🔍 شاشة استعلام واستعراض الفواتير":
    st.title("🔍 شاشة كود الفواتير والاستعلام الجاهز للطباعة")
    conn = get_connection()
    invoices_df = pd.read_sql_query("""
        SELECT inv.id, inv.invoice_number AS 'رقم الفاتورة', inv.invoice_date AS 'التاريخ', 
               p.name AS 'العميل', w.name AS 'المخزن', inv.net_amount AS 'الصافي النهائي', u.full_name AS 'محرر الفاتورة'
        FROM invoices inv JOIN partners p ON inv.partner_id = p.id
        JOIN warehouses w ON inv.warehouse_id = w.id JOIN users u ON inv.sales_rep_id = u.id ORDER BY inv.id DESC
    """, conn)
    
    if invoices_df.empty:
        st.info("لا توجد فواتير صادرة حتى الآن.")
    else:
        st.dataframe(invoices_df, use_container_width=True)
        sel_inv_num = st.selectbox("اختر رقم الفاتورة للطباعة والمعاينة:", invoices_df['رقم الفاتورة'].tolist())
        
        if sel_inv_num:
            inv_row = pd.read_sql_query("""
                SELECT inv.*, p.name AS customer_name, p.phone AS customer_phone, p.address AS customer_address, u.full_name AS sales_rep
                FROM invoices inv JOIN partners p ON inv.partner_id = p.id JOIN users u ON inv.sales_rep_id = u.id WHERE inv.invoice_number = ?
            """, conn, params=(sel_inv_num,)).iloc[0]
            
            items_inv = pd.read_sql_query("""
                SELECT i.code, i.name, ii.quantity, ii.unit_price, ii.total_price
                FROM invoice_items ii JOIN items i ON ii.item_id = i.id WHERE ii.invoice_id = ?
            """, conn, params=(inv_row['id'],))
            
            st.markdown(f"""
                <div class="printable-invoice invoice-box">
                    <div class="invoice-header" style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div class="invoice-title">💻 TOWERTECH IT SYSTEMS</div>
                            <div>شركة تاورتيك لتكنولوجيا المعلومات والمعدات</div>
                            <div>القاهرة - مصر | هاتف: 01000000000</div>
                        </div>
                        <div style="text-align:left;">
                            <h3>فاتورة مبيعات</h3>
                            <b>رقم الفاتورة:</b> {inv_row['invoice_number']}<br>
                            <b>التاريخ:</b> {inv_row['invoice_date']}
                        </div>
                    </div>
                    
                    <table style="width:100%; margin-bottom:20px; border-collapse:collapse;">
                        <tr>
                            <td><b>السيد العميل:</b> {inv_row['customer_name']}</td>
                            <td><b>المسؤول / المبيعات:</b> {inv_row['sales_rep']}</td>
                        </tr>
                        <tr>
                            <td><b>العنوان:</b> {inv_row['customer_address']}</td>
                            <td><b>الهاتف:</b> {inv_row['customer_phone']}</td>
                        </tr>
                    </table>
                    
                    <table border="1" style="width:100%; border-collapse:collapse; text-align:center; margin-bottom:20px;">
                        <thead style="background-color:#f1f5f9;">
                            <tr>
                                <th>الكود</th><th>اسم الصنف / البيان</th><th>الكمية</th><th>سعر الوحدة</th><th>الإجمالي</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join([f"<tr><td>{r['code']}</td><td>{r['name']}</td><td>{r['quantity']}</td><td>{r['unit_price']:,.2f}</td><td>{r['total_price']:,.2f}</td></tr>" for _, r in items_inv.iterrows()])}
                        </tbody>
                    </table>
                    
                    <div style="text-align:left; font-size:16px;">
                        <p><b>الإجمالي:</b> {inv_row['total_amount']:,.2f} ج.م</p>
                        <p><b>ضريبة القيمة المضافة:</b> {inv_row['tax_amount']:,.2f} ج.م</p>
                        <h3 style="color:#0284c7;"><b>الصافي النهائي:</b> {inv_row['net_amount']:,.2f} ج.م</h3>
                    </div>
                    <hr>
                    <div style="text-align:center; font-size:12px; color:#64748b;">
                        شكراً لتعاملكم مع Towertech IT Systems - الفاتورة معتمدة إلكترونياً
                    </div>
                </div>
            """, unsafe_allow_html=True)
            st.button("🖨️ اضغط Ctrl+P للطباعة مقاس A4")
    conn.close()

# ==========================================
# 14. شاشة (9): التقارير الاستعلامية التفصيلية
# ==========================================
elif choice == "📜 التقارير الاستعلامية والتشغيلية":
    st.title("📜 التقارير الاستعلامية التفصيلية")
    conn = get_connection()
    rep_type = st.selectbox("اختر التقرير المطلوبة:", [
        "استعلام عن صنف (الموقف الحالي وخلال فترة)",
        "استعلام عن مورد (الموقف الحالي وخلال فترة)",
        "استعلام عن عميل (الموقف الحالي وخلال فترة)",
        "استعلام عن رصيد وجرد مخزن محدد",
        "تقييم قيمة الرصيد بالصنف ومحتوى المخزن",
        "استعلام مزدوج (عميل/مورد) - مشتريات ومبيعات",
        "حركة اذون الصرف خلال فترة",
        "حركة اذون التوريد خلال فترة",
        "حركة المرتجعات خلال فترة",
        "تقرير حركة التحويلات بين المخازن",
        "تقرير الفواتير الصادرة تفصيلي"
    ])
    
    c1, c2, c3 = st.columns(3)
    s_date = c1.date_input("من تاريخ", value=datetime.date.today() - datetime.timedelta(days=30))
    e_date = c2.date_input("إلى تاريخ", value=datetime.date.today())
    show_charts = c3.checkbox("📊 عرض الرسوم البيانية (Charts)", value=True)
    st.markdown("---")
    
    if "صنف" in rep_type:
        items_list = pd.read_sql_query("SELECT id, name FROM items", conn)
        sel_item = st.selectbox("اختر الصنف:", items_list['name'].tolist()) if not items_list.empty else None
        if sel_item:
            df_res = pd.read_sql_query("""
                SELECT t.trans_date AS 'التاريخ', t.trans_type AS 'نوع الحركة', w.name AS 'المخزن',
                       t.quantity AS 'الكمية', t.unit_price AS 'سعر الوحدة', t.total_price AS 'الإجمالي',
                       COALESCE(p.name, 'غير محدد') AS 'الجهة/الشريك', t.requester_name AS 'المسؤول/المستلم'
                FROM transactions t JOIN items i ON t.item_id = i.id JOIN warehouses w ON t.warehouse_id = w.id
                LEFT JOIN partners p ON t.partner_id = p.id WHERE i.name = ? AND t.trans_date BETWEEN ? AND ?
            """, conn, params=(sel_item, s_date, e_date))
            st.dataframe(df_res, use_container_width=True)
            if show_charts and not df_res.empty:
                st.bar_chart(df_res.groupby('نوع الحركة')['الكمية'].sum())
                
    elif "تحويلات" in rep_type:
        df_res = pd.read_sql_query("""
            SELECT t.trans_date AS 'التاريخ', t.trans_type AS 'الحركة', w1.name AS 'من مخزن', w2.name AS 'إلى مخزن',
                   i.name AS 'الصنف', t.quantity AS 'الكمية', t.requester_name AS 'المسؤول'
            FROM transactions t JOIN warehouses w1 ON t.warehouse_id = w1.id
            LEFT JOIN warehouses w2 ON t.dest_warehouse_id = w2.id JOIN items i ON t.item_id = i.id
            WHERE t.trans_type LIKE '%تحويل%' AND t.trans_date BETWEEN ? AND ? ORDER BY t.trans_date DESC
        """, conn, params=(s_date, e_date))
        st.dataframe(df_res, use_container_width=True)

    else:
        df_res = pd.read_sql_query("""
            SELECT t.trans_date AS 'التاريخ', t.trans_type AS 'الحركة', i.name AS 'الصنف', t.quantity AS 'الكمية', t.total_price AS 'الإجمالي'
            FROM transactions t JOIN items i ON t.item_id = i.id WHERE t.trans_date BETWEEN ? AND ?
        """, conn, params=(s_date, e_date))
        st.dataframe(df_res, use_container_width=True)

    if 'df_res' in locals() and not df_res.empty:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            df_res.to_excel(w, index=False)
        st.download_button("📥 تصدير التقرير لـ Excel", buf.getvalue(), f"Towertech_Report_{datetime.date.today()}.xlsx")
    conn.close()

# ==========================================
# 15. شاشة (10): تقارير الإدارة الاستراتيجية
# ==========================================
elif choice == "👑 تقارير الإدارة الاستراتيجية والاحصائيات":
    st.title("👑 تقارير الإدارة والإحصائيات الاستراتيجية")
    conn = get_connection()
    c1, c2 = st.columns(2)
    s_d = c1.date_input("من تاريخ", value=datetime.date.today() - datetime.timedelta(days=90))
    e_d = c2.date_input("إلى تاريخ", value=datetime.date.today())
    st.markdown("---")
    
    st.subheader("🥇 أكثر الموردين حجماً للمشتروات والمعاملات")
    df_sup = pd.read_sql_query("""
        SELECT p.name AS 'المورد', COUNT(t.id) AS 'عدد الأذون', SUM(t.quantity) AS 'إجمالي القطع', SUM(t.total_price) AS 'حجم المعاملات (ج.م)'
        FROM transactions t JOIN partners p ON t.partner_id = p.id
        WHERE t.trans_type = 'إضافة/توريد' AND t.trans_date BETWEEN ? AND ? GROUP BY p.id ORDER BY SUM(t.total_price) DESC
    """, conn, params=(s_d, e_d))
    st.dataframe(df_sup, use_container_width=True)
    
    st.subheader("🏆 أكبر العملاء حجماً للمبيعات والفواتير")
    df_cust = pd.read_sql_query("""
        SELECT p.name AS 'العميل', COUNT(inv.id) AS 'عدد الفواتير', SUM(inv.net_amount) AS 'إجمالي المسحوبات (ج.م)'
        FROM invoices inv JOIN partners p ON inv.partner_id = p.id
        WHERE inv.invoice_date BETWEEN ? AND ? GROUP BY p.id ORDER BY SUM(inv.net_amount) DESC
    """, conn, params=(s_d, e_d))
    st.dataframe(df_cust, use_container_width=True)
    conn.close()

# ==========================================
# 16. شاشة (11): إدارة المستخدمين وتغيير كلمة السر
# ==========================================
elif choice == "⚙️ إدارة المستخدمين وتغيير كلمات السر":
    if st.session_state['user_role'] != 'مدير النظام':
        st.error("مخصص لمدير النظام فقط.")
    else:
        st.title("⚙️ إدارة المستخدمين والصلاحيات")
        conn = get_connection()
        t1, t2 = st.tabs(["إنشاء حساب جديد", "تغيير كلمة السر"])
        
        with t1:
            with st.form("u_f", clear_on_submit=True):
                un = st.text_input("اسم المستخدم (Username)*")
                fn = st.text_input("الاسم الكامل*")
                pw = st.text_input("كلمة السر*", type="password")
                rl = st.selectbox("دور الموظف والصلاحية*", ["مسؤول مخازن", "ممثل مبيعات", "مدير النظام"])
                if st.form_submit_button("إنشاء الحساب"):
                    if un and pw and fn:
                        try:
                            cursor = conn.cursor()
                            cursor.execute("INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)", (un.strip(), hash_password(pw), fn.strip(), rl))
                            conn.commit()
                            st.success("تم التكويد بنجاح!")
                        except:
                            st.error("اسم المستخدم مكرر.")
        with t2:
            u_df = pd.read_sql_query("SELECT username FROM users", conn)
            su = st.selectbox("اختر المستخدم:", u_df['username'].tolist())
            npw = st.text_input("كلمة السر الجديدة", type="password")
            if st.button("تحديث كلمة السر"):
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET password = ? WHERE username = ?", (hash_password(npw), su))
                conn.commit()
                st.success("تم التحديث بنجاح!")
                
        st.dataframe(pd.read_sql_query("SELECT id, username, full_name, role, created_at FROM users", conn), use_container_width=True)
        conn.close()