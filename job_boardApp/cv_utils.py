import io

def extract_cv_text(uploaded_file):
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    uploaded_file.seek(0)  

    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    if name.endswith(".docx"):
        import docx
        document = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)

    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore")

    return ""