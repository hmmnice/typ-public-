import sqlite3
from flask import jsonify
import faiss
import numpy as np
import pickle
import json

DB_FILE = "database/meetings.db"

def save_transcript_to_db(transcript):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("INSERT INTO meetings (transcript) VALUES (?)", (transcript,))
    meeting_id = cursor.lastrowid  # Get the newly inserted meeting ID

    conn.commit()
    conn.close()

    return meeting_id  # Return the ID so we can use it later 


def save_summary_to_db(meeting_id, summary, rag_chunks):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Convert rag_chunks list to JSON string
    rag_chunks_str = json.dumps(rag_chunks)

    # Check if the meeting ID exists
    cursor.execute("SELECT COUNT(*) FROM meetings WHERE id = ?", (meeting_id,))
    exists = cursor.fetchone()[0]

    if exists:
        # Update the existing row with the new summary and rag_chunks
        cursor.execute("""
            UPDATE meetings 
            SET summary = ?, transcript_chunks = ?
            WHERE id = ?
        """, (summary, rag_chunks_str, meeting_id))
        
        conn.commit()
        conn.close()
        return True  # Success
    else:
        conn.close()
        return False  # Meeting ID not found


def get_meeting_ids():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM meetings")
    meetings = cursor.fetchall()
    conn.close()

    return jsonify([{"id": row[0], "name": f"Meeting {row[0]}"} for row in meetings])

def get_meeting_details(meeting_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT transcript, summary FROM meetings WHERE id = ?", (meeting_id,))
    meeting = cursor.fetchone()
    conn.close()

    if meeting:
        return jsonify({"transcript": meeting[0], "summary": meeting[1]})
    return jsonify({"error": "Meeting not found"}), 404


def delete_meeting(meeting_id):
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Ensure foreign keys are enabled (needed per connection in SQLite)
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Delete the meeting (this triggers cascade delete for related records)
    cursor.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    
    conn.commit()
    conn.close()
    print(f"Meeting {meeting_id} and all related data have been deleted.")
    
def load_faiss_index(meeting_id):
    """
    Load FAISS index with embeddings only for the selected `meeting_id`.
    """

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Fetch embeddings for the selected meeting
    cursor.execute("SELECT embedding FROM meeting_embeddings WHERE meeting_id = ?", (meeting_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        print(f"No embeddings found for meeting_id {meeting_id}")
        return None

    # Convert BLOB back to NumPy array
    embedding = pickle.loads(row[0])
    embedding = np.array(embedding).astype('float32')

    # Create FAISS index
    dimension = embedding.shape[1]
    faiss_index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)
    faiss_index.add(embedding)

    return faiss_index




def save_chat_to_db(meeting_id, user_message, bot_response):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Ensure foreign keys are enabled
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Check if the meeting exists
    cursor.execute("SELECT id FROM meetings WHERE id = ?", (meeting_id,))
    if cursor.fetchone() is None:
        print(f"Meeting ID {meeting_id} does not exist. Skipping chat save.")
        conn.close()
        return

    # Insert chat message
    cursor.execute("""
        INSERT INTO chat_history (meeting_id, user_message, bot_response)
        VALUES (?, ?, ?)
    """, (meeting_id, user_message, bot_response))

    conn.commit()
    conn.close()
    print(f"Chat saved successfully for meeting {meeting_id}.")


def get_chat_history(meeting_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_message, bot_response FROM chat_history 
        WHERE meeting_id = ? ORDER BY timestamp ASC
    """, (meeting_id,))
    
    chat_history = cursor.fetchall()
    conn.close()

    return jsonify([{"user": row[0], "bot": row[1]} for row in chat_history])


try:
    with open("conversations/New Recording 6 2.txt", "r") as file:
        transcript = file.read()
except FileNotFoundError:
    transcript = ""
    print("Transcript file not found. Please check the file path.")


# save_transcript_to_db(transcript)