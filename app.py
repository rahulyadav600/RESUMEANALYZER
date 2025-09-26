import streamlit as st
import pandas as pd
import spacy
import base64, time, datetime, os
from pdfminer.high_level import extract_text
from PIL import Image
from utils import insert_user, get_users, load_data, save_data

# Optional: AI embeddings for smart recommendations
from sentence_transformers import SentenceTransformer, util
model = SentenceTransformer('all-MiniLM-L6-v2')

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None

# Setup Streamlit page
st.set_page_config(page_title="Resume Analyzer", page_icon="assets/logo.png", layout="wide")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Helper functions ---
def show_pdf(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="900" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)

def extract_text_from_file(file_path):
    try:
        if file_path.lower().endswith(".pdf"):
            return extract_text(file_path)
        elif file_path.lower().endswith(".docx"):
            import docx2txt
            return docx2txt.process(file_path)
        else:
            with open(file_path,"r",encoding="utf-8",errors="ignore") as f:
                return f.read()
    except:
        return ""

def analyze_resume(text):
    if nlp is None:
        return [], "N/A"
    doc = nlp(text)
    # skills = nouns + ORG/GPE/PERSON entities
    skills = list({chunk.text.lower() for chunk in doc.noun_chunks} | {ent.text for ent in doc.ents if ent.label_ in ["PERSON","ORG","GPE"]})
    # find candidate name
    name = ""
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            name = ent.text
            break
    # experience detection (simple heuristic)
    exp = 0
    for token in doc:
        if token.like_num and "year" in token.head.text.lower():
            exp = int(token.text)
            break
    # candidate level
    level = "Fresher" if exp<3 else "Intermediate" if 3<=exp<=7 else "Experienced"
    return skills, name, exp, level

def recommend_courses(skills, top_n=5):
    course_pool = {
        "data": ["Data Science Course - Coursera", "Machine Learning A-Z - Udemy"],
        "ml": ["Machine Learning A-Z - Udemy", "AI & ML Specialization"],
        "web": ["Full Stack Web Dev - FreeCodeCamp", "React JS Course"],
        "android": ["Android Dev Bootcamp", "Kotlin Android Development"],
        "ios": ["iOS Dev with Swift", "SwiftUI Masterclass"],
        "ui": ["UI/UX Design Bootcamp", "Figma Complete Guide"],
        "ux": ["UI/UX Design Bootcamp", "Figma Complete Guide"]
    }
    recs = []
    for skill in skills:
        s = skill.lower()
        for key in course_pool:
            if key in s:
                recs += course_pool[key]
    return list(dict.fromkeys(recs))[:top_n]

def get_table_download_link(df, filename="data.csv"):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">Download CSV</a>'

# Session state for admin login
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# --- Layout ---
col1, col2 = st.columns([3,1])
with col1:
    if os.path.exists("assets/logo.png"):
        st.image("assets/logo.png", width=500)
    st.title("📄 AI Resume Analyzer")
with col2:
    st.write("")

st.sidebar.markdown("## Menu")
menu = ["User", "Admin"]
choice = st.sidebar.selectbox("Select mode", menu)

# ----------------- USER -----------------
if choice=="User":
    st.subheader("Upload your resume")
    pdf_file = st.file_uploader("Upload PDF/DOCX/TXT", type=["pdf","docx","txt"])
    if pdf_file:
        save_path = os.path.join(UPLOAD_DIR, pdf_file.name)
        with open(save_path,"wb") as f:
            f.write(pdf_file.getbuffer())
        st.success("File uploaded!")
        show_pdf(save_path)

        resume_text = extract_text_from_file(save_path)
        skills, name, exp, level = analyze_resume(resume_text)

        st.markdown(f"### Candidate Name: {name if name else pdf_file.name}")
        st.markdown(f"**Experience (years):** {exp}")
        st.markdown(f"**Level:** {level}")
        st.markdown("### ✅ Extracted Skills")
        st.write(skills if skills else "No skills detected.")

        # Course recommendations
        rec_courses = recommend_courses(skills)
        if rec_courses:
            st.markdown("### 🎓 Recommended Courses")
            for course in rec_courses:
                st.markdown(f"- {course}")

        # Save to JSON
        record = {
            "name": name if name else pdf_file.name,
            "filename": pdf_file.name,
            "skills": skills,
            "experience": exp,
            "level": level,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_path": save_path
        }
        insert_user(record)
        st.success("Saved successfully!")

    st.markdown("---")
    st.markdown("Developed by **Algorithm Avengers**")

# ----------------- ADMIN -----------------
else:
    st.subheader("🔒 Admin Panel")
    if not st.session_state.admin_authenticated:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            if submitted:
                if username=="rahul" and password=="rahul22":
                    st.session_state.admin_authenticated=True
                    st.success("Admin login successful!")
                else:
                    st.error("Invalid credentials")
        st.stop()

    # Admin authenticated
    st.markdown("**Welcome Admin**")
    users = get_users()
    if users:
        df = pd.DataFrame(users)
        st.dataframe(df)
        st.markdown(get_table_download_link(df), unsafe_allow_html=True)

        # Delete entry
        selected_index = st.number_input("Select row index to delete", min_value=0, max_value=len(df)-1, value=0)
        if st.button("Delete Entry"):
            u = users[selected_index]
            if os.path.exists(u.get("file_path","")):
                os.remove(u["file_path"])
            new_users = [x for i,x in enumerate(users) if i!=selected_index]
            save_data({"users":new_users})
            st.success("Entry deleted. Refresh page to see changes.")

        # Download individual resume
        if st.button("Download Selected Resume"):
            u = users[selected_index]
            fp = u.get("file_path","")
            if fp and os.path.exists(fp):
                with open(fp,"rb") as f:
                    data = f.read()
                b64 = base64.b64encode(data).decode()
                href = f'<a href="data:file/octet-stream;base64,{b64}" download="{os.path.basename(fp)}">Download {os.path.basename(fp)}</a>'
                st.markdown(href, unsafe_allow_html=True)
            else:
                st.warning("File not found.")
    else:
        st.info("No users uploaded resumes yet.")

    if st.button("Logout"):
        st.session_state.admin_authenticated=False
        st.success("Logged out successfully.")
