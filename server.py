import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import whisperx
from datetime import timedelta

import torch
from database.db_manager import save_transcript_to_db, get_meeting_ids, get_meeting_details,save_summary_to_db,save_chat_to_db,get_chat_history
from rag_pipeline import store_embeddings, load_faiss_index, retrieve
from rag_model import chat_pipeline,chat_with_model
from summariser import summarise_pipeline
from database.database import init_db
import gc

app = Flask(__name__)
CORS(app)

init_db()

@app.route('/ping', methods=['GET'])
def ping():
    return "OK", 200

device = "cuda"
batch_size = 4
compute_type = "float16"
hf_token = "hf_TOKEN"
model = whisperx.load_model("small", device, compute_type=compute_type, language="en")

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    audio_file = request.files['file']
    file_path = f"./uploads/{audio_file.filename}"
    audio_file.save(file_path)

    audio = whisperx.load_audio(file_path)
    result = model.transcribe(audio, batch_size=batch_size, language="en")
    model_a, metadata = whisperx.load_align_model(language_code="en", device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

    diarize_model = whisperx.DiarizationPipeline(use_auth_token=hf_token, device=device)
    diarize_segments = diarize_model(audio, min_speakers=2, max_speakers=3)
    result = whisperx.assign_word_speakers(diarize_segments, result)

    conversation = []
    for segment in result["segments"]:
        speaker = segment.get("speaker", "Unknown")
        text = segment["text"]
        conversation.append(f"{speaker}: {text}")

    os.remove(file_path)

    transcript_text = "\n".join(conversation)
    meeting_id = save_transcript_to_db(transcript_text)  

    torch.cuda.empty_cache()
    gc.collect()

    summary, chunks = summarise_pipeline(transcript_text)
    save_summary_to_db(meeting_id,summary,chunks)
    store_embeddings(meeting_id=meeting_id ,summary_chunks=chunks)

    return jsonify({
        "message": "Transcript saved successfully",
        "meeting_id": meeting_id,
        "conversation": conversation
    })

import traceback  

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        data = request.get_json(force=True)

        user_message = data.get('message', '').strip()
        meeting_id = int(data.get('meeting_id', None))

        if not user_message or meeting_id is None:
            print("Error: Missing message or meeting_id")
            return jsonify({"reply": "Please provide a message and select a meeting."}), 400

        results = retrieve(user_message,meeting_id,5)

        extracted_contexts = [item["context"] for item in results if "context" in item]
        context_str = "\n".join(extracted_contexts)  

        reply = chat_with_model(user_input=user_message,context=context_str)

        if "assistant" in reply:
            reply = reply.split("assistant", 1)[-1].strip(': ')

        print("Saving chat to database...")
        save_chat_to_db(meeting_id, user_message, reply)

        return jsonify({"reply": reply})

    except Exception as e:
        print("Chat endpoint error:", str(e))
        traceback.print_exc()  
        return jsonify({"error": str(e)}), 500

@app.route('/get_meeting_ids', methods=['GET'])
def get_meetings():
    return get_meeting_ids() 

@app.route('/get_meeting/<int:meeting_id>', methods=['GET'])
def get_meeting(meeting_id):
    return get_meeting_details(meeting_id)

@app.route('/get_chat_history/<int:meeting_id>', methods=['GET'])
def get_history(meeting_id):
    return get_chat_history(meeting_id)

if __name__ == '__main__':

    app.run(host='0.0.0.0', port=5000, debug=False)