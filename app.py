import streamlit as st
import pandas as pd
import time
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

# Azure credentials
endpoint = st.secrets['ENDPOINT']
key = st.secrets["KEY"]
client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))

# Initialize session state
if "annotations" not in st.session_state:
    st.session_state.annotations = []

if "processed_images" not in st.session_state:
    st.session_state.processed_images = set()

# OCR extraction
def extract_annotations(image_bytes):
    poller = client.begin_analyze_document("prebuilt-document", document=image_bytes)
    result = poller.result()

    kv_pairs = set()
    key_texts = set()
    value_texts = set()

    for kv in result.key_value_pairs:
        if kv.key and kv.value:
            key = kv.key.content.strip()
            value = kv.value.content.strip()
            kv_pairs.add(f"{key}: {value}")
            key_texts.add(key)
            value_texts.add(value)

    table_texts = []
    for ti, table in enumerate(result.tables):
        table_texts.append(f"Table {ti + 1}:")
        for cell in table.cells:
            row = cell.row_index
            col = cell.column_index
            text = cell.content.strip()
            table_texts.append(f"row {row}, col {col}: {text}")

    table_text_set = set([c.split(": ", 1)[-1] for c in table_texts if ": " in c])

    other_details = []
    for para in result.paragraphs:
        text = para.content.strip()
        if text and text not in key_texts and text not in value_texts and text not in table_text_set:
            other_details.append(text)

    return kv_pairs, table_texts, other_details

# UI
st.title("🧾 Medical Report Annotation Tool (5s rate-limit safe)")

uploaded_files = st.file_uploader(
    "Upload medical report images (multiple)", type=["png", "jpg", "jpeg"], accept_multiple_files=True
)

if uploaded_files:
    st.info("Processing will begin with 5-second delay between each image to avoid hitting the API rate limit.")

    for file in uploaded_files:
        if file.name in st.session_state.processed_images:
            st.write(f"✅ Already processed: {file.name}")
            continue

        with st.spinner(f"🔍 Processing {file.name}..."):
            kvs, tables, others = extract_annotations(file)

            new_record = {
                "image": file.name,
                "key_value_pair": "\n".join(sorted(kvs)),
                "table": "\n".join(tables),
                "other_details": "\n".join(others)
            }

            st.session_state.annotations.append(new_record)
            st.session_state.processed_images.add(file.name)

            st.success(f"✅ Done: {file.name}")
            time.sleep(5)  # Respect rate limit

# Show all annotations
if st.session_state.annotations:
    st.subheader("📋 All Annotated Records in this Session")
    df = pd.DataFrame(st.session_state.annotations)
    st.dataframe(df)

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download CSV", data=csv, file_name="annotated_reports.csv", mime="text/csv")
