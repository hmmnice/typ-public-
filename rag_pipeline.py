import sqlite3
import numpy as np
from sentence_transformers import SentenceTransformer
import pickle  
from database.db_manager import load_faiss_index
import faiss
from rank_bm25 import BM25Okapi
import nltk
from nltk.tokenize import word_tokenize
import json

nltk.download('punkt')
nltk.download('punkt_tab')

DB_FILE = "database/meetings.db"

embedding_model = SentenceTransformer("jinaai/jina-embeddings-v3", trust_remote_code=True)

def store_embeddings(meeting_id,summary_chunks):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if not summary_chunks or not isinstance(summary_chunks, list):
        print(f"Error: summary_chunks is empty or not a list for meeting_id {meeting_id}")
        return

    summary_chunks = [str(chunk) for chunk in summary_chunks if isinstance(chunk, str) and chunk.strip()]

    if not summary_chunks:
        print(f"Error: No valid text found in summary_chunks for meeting_id {meeting_id}")
        return

    embedding = embedding_model.encode(summary_chunks)  

    embedding = np.array(embedding).astype("float32")

    embedding_blob = pickle.dumps(embedding)

    cursor.execute("INSERT OR REPLACE INTO meeting_embeddings (meeting_id, embedding) VALUES (?, ?)", 
                    (meeting_id, embedding_blob))

    conn.commit()
    conn.close()
    print("Embeddings stored successfully!")

def retrieve(query, meeting_id, top_k):
    """
    Perform hybrid FAISS + BM25 retrieval, restricted to a specific `meeting_id`.
    """

    faiss_index = load_faiss_index(meeting_id)
    if faiss_index is None:
        return []

    query_embedding = embedding_model.encode([query]).astype('float32')

    similarities, indices = faiss_index.search(query_embedding, top_k)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT transcript_chunks FROM meetings WHERE id = ?", (meeting_id,))
    transcript_data = cursor.fetchone()
    conn.close()

    if not transcript_data:
        return []

    transcript_chunks = json.loads(transcript_data[0])

    if not isinstance(transcript_chunks, list):
        return []

    bm25 = BM25Okapi(transcript_chunks)
    tokenized_query = word_tokenize(query.lower())
    bm25_scores_raw = bm25.get_scores(tokenized_query)

    dense_scores = {idx: similarities[0][idx] if idx < len(similarities[0]) else 0 for idx in range(len(transcript_chunks))}
    bm25_scores = {idx: bm25_scores_raw[idx] if idx < len(bm25_scores_raw) else 0 for idx in range(len(transcript_chunks))}

    combined_scores = {}
    for idx in range(len(transcript_chunks)):
        score_dense = dense_scores.get(idx, 0)
        score_bm25 = bm25_scores.get(idx, 0)
        combined_scores[idx] = score_dense + score_bm25  

    ranked_results = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    final_results = [{"meeting_id": meeting_id, "context": transcript_chunks[idx], "score": combined_scores[idx]} for idx, _ in ranked_results]

    return final_results