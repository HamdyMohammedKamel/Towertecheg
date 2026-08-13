import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib
import io
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. تهيئة الصفحة والتحكم في المظهر والتنسيق
# ==========================================
st.set_page_config(
    page_title="Towertech - نظام إدارة المخازن",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# تطبيق تنسيقات CSS لتحسين الواجهة باللغة العربية وإظهار هوية Towertech
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
        direction: RTL;
        text-align: right;
    }
    
    .stApp {
        background-color: #f8fafc;
    }
    
    /* هيدر وشعار Towertech */
    .brand-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    
    .brand-logo {
        font-size: 32px;
        font-weight: 800;
        color: #38bdf8;
        letter-spacing: 2px;
        margin: 0;
    }
    
    .brand-subtitle {
        font-size: 16px;
        color: #94a3b8;
        margin-top: 5px;
    }
    
    /* بطاقات المقاييس KPIs */
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        border-right: 5px solid #0284c7;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    
    /* تنبيهات المخزون */
    .stAlert {
        border-radius: 8px;
    }
    
    /* أزرار وحقول المدخلات */
    .stButton>button {
        width: 100%;
        background-color: #0284c7;
        color: white;
        font-weight: 600;
        border-radius: 8px;
        border: none;
        padding: 8px 16px;
    }
    .stButton>button:hover {
        background-color: #0369a1;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. إدارة قاعدة البيانات SQLite
# ==========================================
DB_FILE = "towertech_inventory.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'User',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # جدول المخازن (المخزن الرئيسي والمخازن الفرعية)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warehouses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            location TEXT,
            is_main INTEGER DEFAULT 0
        )
    ''')
    
    # جدول الأصناف
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            unit TEXT DEFAULT 'قطعة',
            min_quantity INTEGER DEFAULT 5,
            notes TEXT
        )
    ''')
    
    # جدول رصيد الأصناف في المخازن
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
    
    # جدول حركات المخزون (صرف / توريد / مرتجع) مع التاريخ الإجباري
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trans_date DATE NOT NULL,
            trans_type TEXT NOT NULL, -- 'توريد/إضافة', 'صرف', 'مرتجع'
            warehouse_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL DEFAULT 0.0,
            reference_no TEXT,
            notes TEXT,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            FOREIGN KEY (item_id) REFERENCES items(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # إضافة حساب الأدمن الافتراضي والمخزن الرئيسي إن لم يوجدا
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
            ('admin', hash_password('admin123'), 'مدير النظام', 'Admin')
        )
        
    cursor.execute("SELECT * FROM warehouses WHERE is_main = 1")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO warehouses (name, location, is_main) VALUES (?, ?, ?)",
            ('المخزن الرئيسي', 'المقر الرئيسي - Towertech', 1)
        )
        
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 3. إدارة جلسة المستخدم (Session State)
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

# ==========================================
# 4. دالة عرض الشعار الشامل
# ==========================================
def render_brand_header():
    st.markdown("""
        <div class="brand-header">
            <div class="brand-logo">⚡ TOWERTECH INVENTORY ⚡</div>
            <div class="brand-subtitle">نظام إدارة المخازن الذكي والمستودعات الفرعية</div>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# 5. شاشة تسجيل الدخول
# ==========================================
def login_screen():
    render_brand_header()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("🔑 تسجيل الدخول للنظام")
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
                st.success(f"مرحباً بك، {user['full_name']}")
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة السر غير صحيحة")

if not st.session_state['logged_in']:
    login_screen()
    st.stop()

# ==========================================
# 6. القائمة الجانبية والشريط العلوي
# ==========================================
with st.sidebar:
    st.markdown("### 🏢 Towertech Systems")
    st.image("https://img.icons8.com/color/96/000000/warehouse.png", width=80)
    st.write(f"👤 **المستخدم:** {st.session_state['full_name']}")
    st.write(f"المستوى: `{st.session_state['user_role']}`")
    st.markdown("---")
    
    menu_options = [
        "📊 لوحة التحكم والمخزون الحالي",
        "➕ إضافة صنف جديد",
        "🔄 تسجيل حركة (صرف / توريد / مرتجع)",
        "📈 التقارير الشاملة والتحليلات",
        "🏭 إدارة المخازن الفرعية"
    ]
    
    if st.session_state['user_role'] == 'Admin':
        menu_options.append("⚙️ إدارة المستخدمين وكلمات السر")
        
    choice = st.radio("انتقل إلى الشاشة:", menu_options)
    
    st.markdown("---")
    if st.button("🚪 تسجيل الخروج"):
        st.session_state['logged_in'] = False
        st.rerun()

# عرض الشعار في كل الشاشات
render_brand_header()

# ==========================================
# 7. شاشة (1): لوحة التحكم ومراجعة المخزون الحالي + التنبيهات
# ==========================================
if choice == "📊 لوحة التحكم والمخزون الحالي":
    st.title("📊 لوحة التحكم ومراجعة المخزون الحالي")
    
    conn = get_connection()
    
    # اختيار المخزن للتصفية
    warehouses_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    wh_options = {"الكل": None}
    for _, row in warehouses_df.iterrows():
        wh_options[row['name']] = row['id']
        
    selected_wh_name = st.selectbox("تصفية حسب المخزن:", list(wh_options.keys()))
    selected_wh_id = wh_options[selected_wh_name]
    
    # استعلام المخزون الحالي
    query = """
        SELECT 
            w.name AS 'المخزن',
            i.code AS 'كود الصنف',
            i.name AS 'اسم الصنف',
            i.category AS 'الفئة',
            i.unit AS 'الوحدة',
            COALESCE(inv.quantity, 0) AS 'الكمية الحالية',
            i.min_quantity AS 'الحد الأدنى'
        FROM items i
        CROSS JOIN warehouses w
        LEFT JOIN inventory inv ON inv.item_id = i.id AND inv.warehouse_id = w.id
    """
    
    if selected_wh_id:
        query += f" WHERE w.id = {selected_wh_id}"
        
    df_stock = pd.read_sql_query(query, conn)
    conn.close()
    
    # كروت الإحصائيات السريعة
    total_items = len(df_stock['كود الصنف'].unique())
    total_stock = df_stock['الكمية الحالية'].sum()
    low_stock_df = df_stock[df_stock['الكمية الحالية'] <= df_stock['الحد الأدنى']]
    low_stock_count = len(low_stock_df)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("إجمالي الأصناف المسجلة", total_items)
    with c2:
        st.metric("إجمالي كمية المخزون", int(total_stock))
    with c3:
        st.metric("أصناف وصلت للحد الأدنى فأقل", low_stock_count, delta_color="inverse")
        
    st.markdown("---")
    
    # تنبيه إضافي بارز للأصناف المنخفضة
    if low_stock_count > 0:
        st.warning(f"⚠️ **تنبيه هام!** يوجد عدد ({low_stock_count}) صنف كميته تساوي أو أقل من الحد الأدنى المطلوب أعطه الأولوية في التوريد.")
        with st.expander("🚨 عرض الأصناف التي تحتاج إعادة طلب / توريد عاجل"):
            st.dataframe(low_stock_df, use_container_width=True)
            
    st.subheader("📋 تفاصيل المخزون الحالي")
    search_term = st.text_input("🔍 بحث عن صنف (بالاسم أو الكود أو الفئة):")
    
    if search_term:
        df_filtered = df_stock[
            df_stock['اسم الصنف'].str.contains(search_term, case=False, na=False) |
            df_stock['كود الصنف'].str.contains(search_term, case=False, na=False) |
            df_stock['الفئة'].str.contains(search_term, case=False, na=False)
        ]
    else:
        df_filtered = df_stock
        
    st.dataframe(df_filtered, use_container_width=True)

# ==========================================
# 8. شاشة (2): إضافة صنف جديد
# ==========================================
elif choice == "➕ إضافة صنف جديد":
    st.title("➕ إضافة صنف جديد إلى دليل الأصناف")
    
    conn = get_connection()
    warehouses_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    
    with st.form("add_item_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            item_code = st.text_input("كود الصنف (فريد)*", placeholder="مثال: ITEM-1001")
            item_name = st.text_input("اسم الصنف*", placeholder="مثال: كابل ألياف ضوئية 50 متر")
            category = st.text_input("الفئة / التصنيف", placeholder="مثال: شبكات، معدات، قطع غيار")
        with col2:
            unit = st.selectbox("وحدة القياس", ["قطعة", "متر", "كيلو", "كرتونة", "طقم", "جهاز"])
            min_qty = st.number_input("الحد الأدنى للتنبيه*", min_value=0, value=5, step=1)
            notes = st.text_area("ملاحظات إضافية")
            
        st.markdown("##### 📍 تخصيص الكمية الافتراضية المبدئية عند الإنشاء (اختياري):")
        wh_target = st.selectbox("المخزن المبدئي للإضافة", warehouses_df['name'].tolist())
        initial_qty = st.number_input("الكمية المبدئية التأسيسية", min_value=0, value=0)
        
        submitted = st.form_submit_button("💾 حفظ الصنف")
        
        if submitted:
            if not item_code or not item_name:
                st.error("الرجاء ملء كافة الحقول المتبوعة بنجمة (*)")
            else:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO items (code, name, category, unit, min_quantity, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (item_code.strip(), item_name.strip(), category.strip(), unit, min_qty, notes))
                    
                    new_item_id = cursor.lastrowid
                    wh_id = warehouses_df[warehouses_df['name'] == wh_target]['id'].values[0]
                    
                    if initial_qty > 0:
                        cursor.execute("""
                            INSERT INTO inventory (warehouse_id, item_id, quantity)
                            VALUES (?, ?, ?)
                        """, (wh_id, new_item_id, initial_qty))
                        
                        # تسجيل حركة توريد مبدئية
                        cursor.execute("""
                            INSERT INTO transactions 
                            (trans_date, trans_type, warehouse_id, item_id, quantity, unit_price, reference_no, notes, user_id)
                            VALUES (?, 'توريد/إضافة', ?, ?, ?, 0.0, 'رصيد افتتاح', 'إضافة أولية مع إنشاء الصنف', ?)
                        """, (datetime.date.today(), wh_id, new_item_id, initial_qty, st.session_state['user_id']))
                        
                    conn.commit()
                    st.success(f"تم بنجاح إضافة الصنف ({item_name}) إلى النظام!")
                except sqlite3.IntegrityError:
                    st.error("كود الصنف مستخدم من قبل، يرجى أدخال كود مختلف.")
                except Exception as e:
                    st.error(f"حدث خطأ أثناء الحفظ: {e}")
    conn.close()

# ==========================================
# 9. شاشة (3): تسجيل حركة (صرف / توريد / مرتجع)
# ==========================================
elif choice == "🔄 تسجيل حركة (صرف / توريد / مرتجع)":
    st.title("🔄 تسجيل حركة مخزنية جديدة")
    
    conn = get_connection()
    warehouses_df = pd.read_sql_query("SELECT id, name FROM warehouses", conn)
    items_df = pd.read_sql_query("SELECT id, code, name, unit FROM items", conn)
    
    if items_df.empty:
        st.warning("⚠️ لا توجد أصناف مسجلة في النظام بعد. يرجى إضافة صنف جديد أولاً.")
    else:
        with st.form("transaction_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                # التأكيد الإجباري على اختيار التاريخ
                trans_date = st.date_input("تاريخ الحركة (مطلوب)*", value=datetime.date.today())
                trans_type = st.selectbox("نوع الحركة*", ["توريد/إضافة", "صرف", "مرتجع"])
            with c2:
                wh_name = st.selectbox("المخزن المستهدف*", warehouses_df['name'].tolist())
                item_display = st.selectbox(
                    "الصنف*", 
                    items_df.apply(lambda row: f"{row['code']} - {row['name']}", axis=1).tolist()
                )
            with c3:
                quantity = st.number_input("الكمية*", min_value=1, value=1, step=1)
                unit_price = st.number_input("سعر الوحدة (إن وجد)", min_value=0.0, value=0.0, step=0.5)
                
            c4, c5 = st.columns(2)
            with c4:
                ref_no = st.text_input("رقم الإذن / الفاتورة / المرجع", placeholder="REV-2026-001")
            with c5:
                trans_notes = st.text_input("الجهة / البيان / ملاحظات", placeholder="اسم المورد أو القسم المستلم")
                
            btn_submit = st.form_submit_button("🚀 تنفيذ وتسجيل الحركة")
            
            if btn_submit:
                selected_item_code = item_display.split(" - ")[0]
                item_id = items_df[items_df['code'] == selected_item_code]['id'].values[0]
                wh_id = warehouses_df[warehouses_df['name'] == wh_name]['id'].values[0]
                
                cursor = conn.cursor()
                
                # جلب الكمية الحالية للصنف بالمخزن
                cursor.execute(
                    "SELECT quantity FROM inventory WHERE warehouse_id = ? AND item_id = ?",
                    (wh_id, item_id)
                )
                res = cursor.fetchone()
                current_qty = res['quantity'] if res else 0
                
                # التحقق من إمكانية الصرف
                if trans_type == "صرف" and quantity > current_qty:
                    st.error(f"❌ المتبقي في المخزن ({current_qty}) غير كافٍ لصرف الكمية المطلوبة ({quantity}).")
                else:
                    # حساب الكمية الجديدة
                    if trans_type in ["توريد/إضافة", "مرتجع"]:
                        new_qty = current_qty + quantity
                    else:  # صرف
                        new_qty = current_qty - quantity
                        
                    # تحديث أو إضافة الرصيد
                    cursor.execute("""
                        INSERT INTO inventory (warehouse_id, item_id, quantity)
                        VALUES (?, ?, ?)
                        ON CONFLICT(warehouse_id, item_id) DO UPDATE SET quantity = ?
                    """, (wh_id, item_id, new_qty, new_qty))
                    
                    # تسجيل الحركة في الأرشيف التاريخي
                    cursor.execute("""
                        INSERT INTO transactions 
                        (trans_date, trans_type, warehouse_id, item_id, quantity, unit_price, reference_no, notes, user_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (trans_date, trans_type, wh_id, item_id, quantity, unit_price, ref_no, trans_notes, st.session_state['user_id']))
                    
                    conn.commit()
                    st.success(f"✅ تم تسجيل حركة ({trans_type}) بنجاح بتاريخ {trans_date}! الرصيد الجديد: {new_qty}")
    conn.close()

# ==========================================
# 10. شاشة (4): التقارير الشاملة والرسوم البيانية الاختيارية
# ==========================================
elif choice == "📈 التقارير الشاملة والتحليلات":
    st.title("📈 مركز التقارير والتحليلات الشاملة")
    
    conn = get_connection()
    
    st.subheader("⚙️ خيارات التقرير والتصفية")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        report_type = st.selectbox(
            "نوع التقرير المطلوبة", 
            ["تقرير حركة الحركات التفصيلية", "ملخص الحركة حسب نوع الحركة", "تقرير الأصناف الأكثر حركة", "تقرير تقييم المخزون المالي"]
        )
    with col2:
        start_date = st.date_input("من تاريخ", value=datetime.date.today() - datetime.timedelta(days=30))
    with col3:
        end_date = st.date_input("إلى تاريخ", value=datetime.date.today())
    with col4:
        # خيار إظهار الرسوم البيانية اختياري بناءً على طلبك
        show_charts = st.checkbox("📊 إظهار الرسوم البيانية (Graphs & Charts)", value=True)
        
    st.markdown("---")
    
    if report_type == "تقرير حركة الحركات التفصيلية":
        query = """
            SELECT 
                t.trans_date AS 'التاريخ',
                t.trans_type AS 'نوع الحركة',
                w.name AS 'المخزن',
                i.code AS 'كود الصنف',
                i.name AS 'اسم الصنف',
                t.quantity AS 'الكمية',
                t.unit_price AS 'سعر الوحدة',
                (t.quantity * t.unit_price) AS 'الإجمالي',
                t.reference_no AS 'المرجع',
                t.notes AS 'الملاحظات والجهة',
                u.full_name AS 'المستخدم المنفذ'
            FROM transactions t
            JOIN warehouses w ON t.warehouse_id = w.id
            JOIN items i ON t.item_id = i.id
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.trans_date BETWEEN ? AND ?
            ORDER BY t.trans_date DESC, t.id DESC
        """
        df_report = pd.read_sql_query(query, conn, params=(start_date, end_date))
        
        st.write(f"### 📄 سجل الحركات التفصيلية للفترة من {start_date} إلى {end_date}")
        st.dataframe(df_report, use_container_width=True)
        
        if show_charts and not df_report.empty:
            st.markdown("#### 📊 الرسوم البيانية المرفقة بالتقرير:")
            c1, c2 = st.columns(2)
            with c1:
                fig1 = px.pie(df_report, names='نوع الحركة', values='الكمية', title="توزيع الكميات حسب نوع الحركة", hole=0.4)
                st.plotly_chart(fig1, use_container_width=True)
            with c2:
                fig2 = px.bar(df_report, x='التاريخ', y='الكمية', color='نوع الحركة', title="تطور الحركات حسب الأيام")
                st.plotly_chart(fig2, use_container_width=True)

    elif report_type == "ملخص الحركة حسب نوع الحركة":
        query = """
            SELECT 
                t.trans_type AS 'نوع الحركة',
                COUNT(t.id) AS 'عدد الحركات',
                SUM(t.quantity) AS 'إجمالي الكميات',
                SUM(t.quantity * t.unit_price) AS 'إجمالي القيمة المالاي'
            FROM transactions t
            WHERE t.trans_date BETWEEN ? AND ?
            GROUP BY t.trans_type
        """
        df_report = pd.read_sql_query(query, conn, params=(start_date, end_date))
        st.write("### 📊 ملخص حجم الحركات حسب النوع")
        st.dataframe(df_report, use_container_width=True)
        
        if show_charts and not df_report.empty:
            fig = px.bar(df_report, x='نوع الحركة', y='إجمالي الكميات', color='نوع الحركة', text='إجمالي الكميات', title="مقارنة إجمالي الكميات لكل نوع حركة")
            st.plotly_chart(fig, use_container_width=True)

    elif report_type == "تقرير الأصناف الأكثر حركة":
        query = """
            SELECT 
                i.code AS 'كود الصنف',
                i.name AS 'اسم الصنف',
                SUM(t.quantity) AS 'إجمالي حركة الكميات',
                COUNT(t.id) AS 'عدد مرات الحركة'
            FROM transactions t
            JOIN items i ON t.item_id = i.id
            WHERE t.trans_date BETWEEN ? AND ?
            GROUP BY i.id
            ORDER BY SUM(t.quantity) DESC
            LIMIT 10
        """
        df_report = pd.read_sql_query(query, conn, params=(start_date, end_date))
        st.write("### 🔥 أعلى 10 أصناف حركة ودوراناً بالمخازن")
        st.dataframe(df_report, use_container_width=True)
        
        if show_charts and not df_report.empty:
            fig = px.bar(df_report, x='اسم الصنف', y='إجمالي حركة الكميات', title="الأصناف الأعلى حركة في الفترة المحددة")
            st.plotly_chart(fig, use_container_width=True)

    elif report_type == "تقرير تقييم المخزون المالي":
        query = """
            SELECT 
                w.name AS 'المخزن',
                SUM(inv.quantity) AS 'إجمالي القطع المخزنة',
                COUNT(inv.item_id) AS 'عدد الأصناف المتوفرة'
            FROM inventory inv
            JOIN warehouses w ON inv.warehouse_id = w.id
            GROUP BY w.id
        """
        df_report = pd.read_sql_query(query, conn)
        st.write("### 💰 تقييم المخزون الحالي وإجمالي الكميات للمستويات القيادية")
        st.dataframe(df_report, use_container_width=True)
        
        if show_charts and not df_report.empty:
            fig = px.pie(df_report, names='المخزن', values='إجمالي القطع المخزنة', title="توزيع المخزون عبر المخزن الرئيسي والمخازن الفرعية")
            st.plotly_chart(fig, use_container_width=True)

    # إمكانية تصدير التقرير الحالي إلى Excel
    if 'df_report' in locals() and not df_report.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_report.to_excel(writer, sheet_name='Towertech_Report', index=False)
            
        st.download_button(
            label="📥 تصدير التقرير الحالي إلى Excel",
            data=buffer.getvalue(),
            file_name=f"Towertech_Report_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    conn.close()

# ==========================================
# 11. شاشة (5): إدارة المخازن الفرعية
# ==========================================
elif choice == "🏭 إدارة المخازن الفرعية":
    st.title("🏭 إضافة وإدارة المخازن الفرعية")
    
    conn = get_connection()
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("➕ إضافة مخزن فرعي جديد")
        with st.form("add_wh_form", clear_on_submit=True):
            wh_name_input = st.text_input("اسم المخزن الفرعي*")
            wh_loc_input = st.text_input("الموقع / الفرع / المدينة")
            
            btn_add_wh = st.form_submit_button("حفظ المخزن")
            
            if btn_add_wh:
                if not wh_name_input:
                    st.error("يرجى إدخال اسم المخزن الفرعي")
                else:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO warehouses (name, location, is_main) VALUES (?, ?, 0)",
                                       (wh_name_input.strip(), wh_loc_input.strip()))
                        conn.commit()
                        st.success(f"تم إنشاء المخزن الفرعي ({wh_name_input}) بنجاح!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("اسم المخزن موجود بالفعل.")
                        
    with col2:
        st.subheader("📍 قائمة المخازن الحالية بالنظام")
        wh_df = pd.read_sql_query("""
            SELECT id AS 'المعرف', name AS 'اسم المخزن', location AS 'الموقع', 
            CASE WHEN is_main = 1 THEN 'المخزن الرئيسي' ELSE 'مخزن فرعي' END AS 'النوع'
            FROM warehouses
        """, conn)
        st.dataframe(wh_df, use_container_width=True)
        
    conn.close()

# ==========================================
# 12. شاشة (6): إدارة المستخدمين وتغيير كلمة السر (للأدمن فقط)
# ==========================================
elif choice == "⚙️ إدارة المستخدمين وكلمات السر":
    if st.session_state['user_role'] != 'Admin':
        st.error("⛔ هذه الشاشة مخصصة لمدير النظام فقط.")
    else:
        st.title("⚙️ إدارة المستخدمين وصلاحيات الحسابات")
        
        conn = get_connection()
        
        tab1, tab2 = st.tabs(["👤 إنشاء حساب مستخدم جديد", "🔑 تغيير كلمة السر للمستخدمين"])
        
        with tab1:
            st.subheader("إضافة مستخدم جديد للنظام")
            with st.form("new_user_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    new_username = st.text_input("اسم المستخدم (Username)*")
                    new_fullname = st.text_input("الاسم الكامل*")
                with c2:
                    new_password = st.text_input("كلمة السر*", type="password")
                    new_role = st.selectbox("الصلاحية / المستوى", ["User", "Admin"])
                    
                btn_create_user = st.form_submit_button("إنشاء الحساب")
                
                if btn_create_user:
                    if not new_username or not new_password or not new_fullname:
                        st.error("جميع الحقول متبوعة بنجمة مطلوبة.")
                    else:
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
                                (new_username.strip(), hash_password(new_password), new_fullname.strip(), new_role)
                            )
                            conn.commit()
                            st.success(f"تم إنشاء حساب للمستخدم ({new_fullname}) بنجاح!")
                        except sqlite3.IntegrityError:
                            st.error("اسم المستخدم هذا مسجل مسبقاً.")
                            
        with tab2:
            st.subheader("🔑 تغيير كلمة السر لأي مستخدم")
            users_df = pd.read_sql_query("SELECT id, username, full_name FROM users", conn)
            
            selected_user_display = st.selectbox(
                "اختر المستخدم المراد تغيير كلمة السر له:",
                users_df.apply(lambda r: f"{r['username']} ({r['full_name']})", axis=1).tolist()
            )
            
            change_pass_input = st.text_input("كلمة السر الجديدة", type="password")
            if st.button("تحديث كلمة السر"):
                if not change_pass_input:
                    st.error("يرجى إدخال كلمة السر الجديدة")
                else:
                    target_username = selected_user_display.split(" (")[0]
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE users SET password = ? WHERE username = ?",
                        (hash_password(change_pass_input), target_username)
                    )
                    conn.commit()
                    st.success(f"تم بنجاح تغيير كلمة السر للمستخدم {target_username}")
                    
        st.markdown("---")
        st.subheader("📋 قائمة جميع المستخدمين المسجلين")
        all_users = pd.read_sql_query("SELECT id, username, full_name, role, created_at FROM users", conn)
        st.dataframe(all_users, use_container_width=True)
        
        conn.close()
