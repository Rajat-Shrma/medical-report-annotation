import streamlit as st
import pandas as pd
import io
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

# Azure credentials
endpoint = secret['ENDPOINT']
key = secret["KEY"]
client = DocumentAnalysisClient(endpoint=endpoint, credential=AzureKeyCredential(key))

# Initialize session state for annotations
if "annotations" not in st.session_state:
    st.session_state.annotations = []

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

# App UI
st.title("🧾 Medical Report Annotation Tool")

uploaded_file = st.file_uploader("Upload a medical report image", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image_name = uploaded_file.name
    already_processed = any(rec["image"] == image_name for rec in st.session_state.annotations)

    if already_processed:
        st.warning("⚠️ This image has already been annotated in this session.")
    else:
        with st.spinner("🔍 Extracting annotations..."):
            kvs, tables, others = extract_annotations(uploaded_file)

        new_record = {
            "image": image_name,
            "key_value_pair": "\n".join(sorted(kvs)),
            "table": "\n".join(tables),
            "other_details": "\n".join(others)
        }

        st.session_state.annotations.append(new_record)

        st.success("✅ Annotation complete!")

        st.subheader("🔍 Extracted Data:")
        st.text_area("Key-Value Pairs", new_record["key_value_pair"], height=150)
        st.text_area("Tables", new_record["table"], height=150)
        st.text_area("Other Details", new_record["other_details"], height=150)

# Show all annotations in session
if st.session_state.annotations:
    st.subheader("📋 All Annotated Records in this Session")
    df = pd.DataFrame(st.session_state.annotations)
    st.dataframe(df)

    # CSV download
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name="annotated_reports.csv",
        mime="text/csv"
    )
