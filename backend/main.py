import os
import shutil
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pypdf import PdfReader

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama

from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

app = FastAPI(title="Resume Analyzer Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "./uploaded_pdfs"
CHROMA_DIR = "./chroma_db"
os.makedirs(UPLOAD_DIR, exist_ok=True)

embeddings = OllamaEmbeddings(model="nomic-embed-text")
retriever = None
lcel_rag_chain = None

class QueryRequest(BaseModel):
    question: str

class JobMatchRequest(BaseModel):
    job_description: str

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

@app.post("/api/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    job_description: Optional[str] = Form(None)
):
    global retriever, lcel_rag_chain
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 1. Parse PDF natively using pypdf to avoid community deprecations 🛠️
        reader = PdfReader(file_path)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        # Convert raw text into standard LangChain Document format
        docs = [Document(page_content=full_text, metadata={"source": file.filename})]

        # 2. Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)

        if os.path.exists(CHROMA_DIR):
            shutil.rmtree(CHROMA_DIR)

        vector_store = Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=CHROMA_DIR
        )
        retriever = vector_store.as_retriever(search_kwargs={"k": 3})

        # 3. LLM Setup
        llm = ChatOllama(model="llama3.2:3b", temperature=0.3)
        json_llm = ChatOllama(model="llama3.2:3b", temperature=0.1, format="json")

        # 4. Prompt Structure
        prompt = ChatPromptTemplate.from_template(
            "You are an expert HR assistant and resume reviewer.\n"
            "Use the following pieces of retrieved context from the resume to answer the question accurately.\n"
            "If you don't know the answer, say that you don't know.\n\n"
            "Context:\n{context}\n\n"
            "Question: {question}\n\n"
            "Answer:"
        )

        # 5. LCEL RAG Chain
        lcel_rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
        )

        # 6. Base Strategy: Always parse the structured resume summary
        analysis_prompt = ChatPromptTemplate.from_template(
            "You are an ATS (Applicant Tracking System) parser. Analyze the following resume text and extract the details "
            "into a clean, structured JSON format with these exact keys: 'name', 'summary', 'skills', 'experience', 'education'.\n"
            "Keep the item entries concise.\n\n"
            "Resume Text:\n{resume_text}\n\n"
            "Respond ONLY with valid JSON."
        )
        analysis_chain = analysis_prompt | json_llm | JsonOutputParser()
        structured_analysis = analysis_chain.invoke({"resume_text": full_text})

        response_payload = {
            "message": f"Successfully processed {file.filename}",
            "chunks": len(splits),
            "analysis": structured_analysis,
            "match_results": None
        }

        # 7. Conditional Strategy: If job description is provided, run match evaluation
        if job_description and job_description.strip():
            match_prompt = ChatPromptTemplate.from_template(
                "You are an elite corporate recruiter. Compare the candidate's resume text against the provided Job Description.\n"
                "Evaluate them meticulously and output your assessment strictly in JSON format with these exact keys:\n"
                "- 'match_percentage': an integer from 0 to 100\n"
                "- 'matching_skills': a list of strings representing skills present in both\n"
                "- 'missing_skills': a list of key skills requested in the job description but missing or weak in the resume\n"
                "- 'feedback': a short paragraph with actionable advice to tailor the resume for this specific role.\n\n"
                "Job Description:\n{job_desc}\n\n"
                "Resume Text:\n{resume_text}\n\n"
                "Respond ONLY with valid JSON."
            )
            match_chain = match_prompt | json_llm | JsonOutputParser()
            match_results = match_chain.invoke({
                "job_desc": job_description,
                "resume_text": full_text
            })
            response_payload["match_results"] = match_results

        return response_payload

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat(payload: QueryRequest):
    global lcel_rag_chain

    try:
        # Condition A: A PDF was uploaded, use the RAG pipeline
        if lcel_rag_chain is not None:
            response_text = lcel_rag_chain.invoke(payload.question)
            return {"answer": response_text}

        # Condition B: No PDF uploaded, chat directly with LLM
        else:
            llm = ChatOllama(model="llama3.2:3b", temperature=0.3, num_ctx=2048)
            prompt = ChatPromptTemplate.from_template(
                "You are a career coach and professional resume reviewer. Answer the user's question directly and constructively.\n\n"
                "Question: {question}\n\n"
                "Answer:"
            )
            direct_chain = {"question": RunnablePassthrough()} | prompt | llm | StrOutputParser()
            response_text = direct_chain.invoke(payload.question)
            return {"answer": response_text}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
