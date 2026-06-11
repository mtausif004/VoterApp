import streamlit as st
import pandas as pd
import sqlite3
import pypdf
import re

# ডাটাবেজ ফাইল নেম
DB_NAME = "voter_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # pdf_filename কলাম যুক্ত করা হয়েছে সোর্স ট্র্যাক করার জন্য
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            serial_no TEXT,
            name TEXT,
            voter_no TEXT,
            father_name TEXT,
            mother_name TEXT,
            profession TEXT,
            dob TEXT,
            address TEXT,
            area_name TEXT,
            pdf_filename TEXT
        )
    ''')
    conn.commit()
    conn.close()

# ভাঙা বাংলা টেক্সট ও ফন্ট এনকোডিং ঠিক করার উন্নত মেথড
def clean_text(text):
    if not text:
        return ""
    # পিডিএফ এক্সট্র্যাকশনের সময় হওয়া কমন ভুলগুলো ঠিক করা
    replacements = {
        "Ïভাটার": "ভোটার", "িপতা": "পিতা", "িঠকানা": "ঠিকানা",
        "Ïপশা": "پেশা", "জĥ তািরخ": "জন্ম তারিখ", "জĥ তািরখ": "জন্ম তারিখ",
        "জহ তািরখ": "জন্ম তারিখ", "গৃিহনী": "গৃহিনী", "Řিমক": "শ্রমিক",
        "চÿåাম": "চট্টগ্রাম", "মধË": "মধ্য", "এওিচয়া": "এওচিয়া",
        "সাতকািনয়া": "সাতকানিয়া", "ÏমাছাŇৎ": "মোসাম্মৎ", "ÏমাহাŇদ": "মোহাম্মদ"
    }
    for broken, correct in replacements.items():
        text = text.replace(broken, correct)
    return text.strip()

# পিডিএফ থেকে ডাটা রিড করে ডাটাবেজে সেভ করার ফাংশন
def process_pdf(uploaded_file):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # ফাইলের আসল নাম সংরক্ষণ
    filename = uploaded_file.name
    
    reader = pypdf.PdfReader(uploaded_file)
    full_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"
            
    # ভোটার এলাকার নাম ডিটেক্ট করা
    area_match = re.search(r"ভোটার এলাকার নাম:\s*([^\n\r]+)", full_text)
    if not area_match:
        area_match = re.search(r"এলাকার নাম:\s*([^\n\r]+)", full_text)
    
    area_name = area_match.group(1).strip() if area_match else "অজানা এলাকা"
    area_name = clean_text(area_name)

    # রেগুলার এক্সপ্রেশন প্যাটার্ন (বাংলা ও ভাঙা এনকোডিং দুইটাই সাপোর্ট করবে)
    # প্যাটার্ন ১: ভাঙা এনকোডিং টেক্সট এর জন্য
    matches = re.findall(r"(\d{4})\.\s*নাম:\s*(.*?)\s*ভোটার নং:\s*(\d+).*?িপতা:\s*(.*?)\s*মাতা:\s*(.*?)\s*.*?পেশা:\s*(.*?),\s*জ[ĥহ] তাির[খخ]:\s*([\d/]+)\s*.*?িঠকানা:\s*(.*?)(?=\s*\d{4}\.\s*নাম:|$)", full_text, re.DOTALL)
    
    # প্যাটার্ন ২: যদি টেক্সট একদম শুদ্ধ বাংলায় থাকে (ব্যাকআপ)
    if not matches:
        matches = re.findall(r"(\d{4})\.\s*নাম:\s*(.*?)\s*ভোটার নং:\s*(\d+).*?পিতা:\s*(.*?)\s*মাতা:\s*(.*?)\s*পেশা:\s*(.*?),\s*জন্ম তারিখ:\s*([\d/]+)\s*ঠিকানা:\s*(.*?)(?=\s*\d{4}\.\s*নাম:|$)", full_text, re.DOTALL)

    voters_added = 0
    for match in matches:
        serial_no = match[0].strip()
        name = clean_text(match[1])
        voter_no = match[2].strip()
        father_name = clean_text(match[3])
        mother_name = clean_text(match[4])
        profession = clean_text(match[5])
        dob = match[6].strip()
        address = clean_text(match[7])
        
        # একই ভোটার নম্বর ডাটাবেজে অলরেডি আছে কিনা চেক (ডুপ্লিকেট এড়ানো)
        cursor.execute("SELECT id FROM voters WHERE voter_no = ?", (voter_no,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO voters (serial_no, name, voter_no, father_name, mother_name, profession, dob, address, area_name, pdf_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (serial_no, name, voter_no, father_name, mother_name, profession, dob, address, area_name, filename))
            voters_added += 1
            
    conn.commit()
    conn.close()
    return voters_added, area_name

# --- Streamlit UI ড্যাশবোর্ড ---
st.set_page_config(page_title="স্মার্ট ভোটার ডাটাবেজ", layout="wide")
init_db()

st.title("🎯 ভোটার ডিরেক্টরি ম্যানেজার ও স্মার্ট সার্চ")
st.write("পিডিএফ আপলোড করুন। আপনার ডাটা সরাসরি `voter_database.db` ফাইলে চিরস্থায়ীভাবে সোর্স ফাইল নেমসহ সংরক্ষিত থাকবে।")

# সাইডবার কন্ট্রোল
with st.sidebar:
    st.header("📁 পিডিএফ ডাটা ইনপুট")
    uploaded_files = st.file_uploader("একাধিক ভোটার তালিকা (PDF) এখানে ড্রপ করুন", type=["pdf"], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("🔄 ডাটাবেজে যুক্ত করুন"):
            with st.spinner("পিডিএফ প্রসেস হচ্ছে..."):
                for f in uploaded_files:
                    added, area = process_pdf(f)
                    st.success(f"সফল: {f.name} ➡️ {added} জন নতুন ভোটার যুক্ত!")
                    
    st.markdown("---")
    # ডাটাবেজের বর্তমান অবস্থা দেখার জন্য
    conn = sqlite3.connect(DB_NAME)
    total_count = conn.execute("SELECT COUNT(*) FROM voters").fetchone()[0]
    unique_files = conn.execute("SELECT DISTINCT pdf_filename FROM voters").fetchall()
    conn.close()
    
    st.metric(label="ডাটাবেজে মোট ভোটার সংখ্যা", value=total_count)
    st.write(f"মোট সোর্স পিডিএফ ফাইল: {len(unique_files)} টি")
    
    if st.button("⚠️ ডাটাবেজ সম্পূর্ণ মুছুন"):
        conn = sqlite3.connect(DB_NAME)
        conn.execute("DELETE FROM voters")
        conn.commit()
        conn.close()
        st.experimental_rerun()

# সার্চ প্যানেল
st.subheader("🔍 অ্যাডভান্সড সার্চ ফিল্টার")

col1, col2, col3, col4 = st.columns(4)
with col1:
    search_voter_no = st.text_input("ভোটার নম্বর")
    search_name = st.text_input("ভোটারের নাম")
with col2:
    search_serial = st.text_input("সিরিয়াল নম্বর")
    search_father = st.text_input("পিতার নাম")
with col3:
    search_address = st.text_input("ঠিকানা/গ্রাম")
    search_pdf = st.text_input("পিডিএফ ফাইলের নাম (যেমন: 152400...)")
with col4:
    search_prof = st.text_input("পেশা")
    search_dob = st.text_input("জন্ম তারিখ")

# ডাটাবেজ থেকে কুয়েরি তৈরি করা
conn = sqlite3.connect(DB_NAME)
query = "SELECT serial_no, name, voter_no, father_name, mother_name, profession, dob, address, area_name, pdf_filename FROM voters WHERE 1=1"
params = []

if search_voter_no: query += " AND voter_no LIKE ?"; params.append(f"%{search_voter_no}%")
if search_name: query += " AND name LIKE ?"; params.append(f"%{search_name}%")
if search_serial: query += " AND serial_no LIKE ?"; params.append(f"%{search_serial}%")
if search_father: query += " AND father_name LIKE ?"; params.append(f"%{search_father}%")
if search_address: query += " AND address LIKE ?"; params.append(f"%{search_address}%")
if search_pdf: query += " AND pdf_filename LIKE ?"; params.append(f"%{search_pdf}%")
if search_prof: query += " AND profession LIKE ?"; params.append(f"%{search_prof}%")
if search_dob: query += " AND dob LIKE ?"; params.append(f"%{search_dob}%")

df = pd.read_sql_query(query, conn, params=params)
conn.close()

# ফলাফল প্রদর্শন
st.markdown("---")
if not df.empty:
    st.success(f"🔍 অনুসন্ধানে মোট {len(df)} জন ভোটারের তথ্য পাওয়া গেছে।")
    
    # সার্চ করা ডাটাকে CSV হিসেবে ডাউনলোড করার ডাইনামিক নামকরণ
    default_csv_name = "filtered_voter_data.csv"
    if search_pdf:
        # যদি নির্দিষ্ট কোনো পিডিএফ সার্চ করেন, তবে এক্সেল ফাইলের নামও সেই পিডিএফের নামে হবে
        default_csv_name = f"{search_pdf.replace('.pdf', '')}.csv"
        
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label=f"📥 এই ডাটাটি {default_csv_name} হিসেবে ডাউনলোড করুন",
        data=csv_data,
        file_name=default_csv_name,
        mime='text/csv',
    )
    
    st.write("### 🪪 ভোটার আইডি কার্ডসমূহ:")
    
    for i in range(0, len(df), 2):
        card_cols = st.columns(2)
        for idx, col in enumerate(card_cols):
            if i + idx < len(df):
                row = df.iloc[i + idx]
                with col:
                    st.markdown(f"""
                    <div style="border: 1px solid #4CAF50; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #fcfcfc; box-shadow: 1px 1px 4px rgba(0,0,0,0.05);">
                        <span style="background-color: #4CAF50; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; float: right;">সিরিয়াল: {row['serial_no']}</span>
                        <h4 style="color: #2E7D32; margin-top: 0; margin-bottom: 10px;">🗳️ ভোটার তথ্য কার্ড</h4>
                        <p style="margin: 3px 0;"><b>নাম:</b> {row['name']}</p>
                        <p style="margin: 3px 0; color: #C62828;"><b>ভোটার নং:</b> {row['voter_no']}</p>
                        <p style="margin: 3px 0;"><b>পিতার নাম:</b> {row['father_name']}</p>
                        <p style="margin: 3px 0;"><b>মাতার নাম:</b> {row['mother_name']}</p>
                        <p style="margin: 3px 0;"><b>পেশা:</b> {row['profession']} | <b>জন্ম তারিখ:</b> {row['dob']}</p>
                        <p style="margin: 3px 0; font-size: 0.9em; color: #424242;"><b>ঠিকানা:</b> {row['address']}</p>
                        <hr style="margin: 8px 0; border: 0; border-top: 1px solid #eee;">
                        <p style="margin: 0; font-size: 0.75em; color: #757575;">📂 <b>উৎস ফাইল:</b> {row['pdf_filename']}</p>
                    </div>
                    """, unsafe_allow_html=True)
else:
    st.info("কোনো ডাটা পাওয়া যায়নি। অনুগ্রহ করে ফিল্টার চেক করুন অথবা বামপাশের সাইডবার থেকে পিডিএফ আপলোড করুন।")
