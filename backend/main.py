import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Native PDF parsing library
from pypdf import PdfReader

# Vector Store & Splits
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama

# Your preferred LCEL modules 🌟
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document  # Standard text wrapper

app = FastAPI(title="Angular 22 & Ollama RAG Backend")

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

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
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
        llm = ChatOllama(model="llama3:latest", temperature=0.3)

        # 4. Prompt Structure
        prompt = ChatPromptTemplate.from_template(
            "You are an assistant for question-answering tasks.\n"
            "Use the following pieces of retrieved context to answer the question.\n"
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

        return {"message": f"Successfully processed {file.filename}", "chunks": len(splits)}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


def get_direct_chat_chain():
    llm = ChatOllama(model="llama3:latest", temperature=0.3)
    prompt = ChatPromptTemplate.from_template(
        "You are a helpful AI assistant. Answer the user's question directly.\n\n"
        "Question: {question}\n\n"
        "Answer:"
    )
    return (
        {"question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

@app.post("/api/chat")
async def chat(payload: QueryRequest):
    global lcel_rag_chain

    try:
        # Condition A: A PDF was uploaded, use the RAG pipeline 📄
        if lcel_rag_chain is not None:
            response_text = lcel_rag_chain.invoke(payload.question)
            return {"answer": response_text}

        # Condition B: No PDF uploaded, chat directly with Llama 3 🧠
        else:
            direct_chain = get_direct_chat_chain()
            response_text = direct_chain.invoke(payload.question)
            return {"answer": response_text}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
