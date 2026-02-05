import torch
from transformers import AutoTokenizer, LlamaForCausalLM, BitsAndBytesConfig, pipeline
from langchain.text_splitter import RecursiveCharacterTextSplitter
import gc
from tqdm import tqdm
import time

def summarise_pipeline(transcript):
    """
    Summarizes a long transcript in two stages:
    1) Summarize each chunk individually with minimal instructions.
    2) Combine chunk summaries and summarize them again with minimal instructions.
    Returns:
        final_summary (str): The consolidated summary for the entire transcript.
        summary_chunks (dict): chunk -> partial summary mapping
    """

    model_name = "meta-llama/Llama-3.2-3B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    tokenizer.pad_token = tokenizer.eos_token

    quant_config = BitsAndBytesConfig(load_in_8bit=True)
    model = LlamaForCausalLM.from_pretrained(
        model_name,
        device_map="auto",
        quantization_config=quant_config,
        torch_dtype=torch.float16
    )

    if torch.cuda.is_available():
        model = torch.compile(model)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    text_gen_pipeline = pipeline(
        task="text-generation",
        model=model,
        tokenizer=tokenizer,
    )

    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n"],
        chunk_size=1200,
        chunk_overlap=200
    )
    docs = text_splitter.create_documents([transcript])

    def get_optimal_batch_size():
        """Dynamically adjust batch size based on free GPU memory."""
        if torch.cuda.is_available():
            total_memory = torch.cuda.get_device_properties(0).total_memory
            reserved_memory = torch.cuda.memory_reserved(0)
            free_memory = total_memory - reserved_memory
            if free_memory > 10e9:
                return 16
            elif free_memory > 6e9:
                return 8
            else:
                return 4
        else:
            return 2

    batch_size = get_optimal_batch_size()
    print(f"Using batch size: {batch_size}")

    def batch_summarize_chunks(prompts, max_new_tokens=200):
        """
        Summarize a list of chunk-prompts in small batches using `text_gen_pipeline`.
        Returns a list of summarized text, one per prompt.
        """
        results = []
        total = (len(prompts) + batch_size - 1) // batch_size

        for i in tqdm(range(0, len(prompts), batch_size), total=total, desc="Summarizing Chunks"):
            batch_prompts = prompts[i : i + batch_size]
            outputs = text_gen_pipeline(
                batch_prompts,
                max_new_tokens=max_new_tokens,
                do_sample=False
            )

            for out in outputs:

                text = out[0]["generated_text"]
                results.append(text)

            torch.cuda.empty_cache()
            gc.collect()

        return results

    chunk_prompts = [
        f"""Summarize the following text in concise bullet points. 
Return ONLY the bullet points without repeating the text:

TEXT:
{doc.page_content}

BULLET POINT SUMMARY:
"""
        for doc in docs
    ]

    chunk_summaries_raw = batch_summarize_chunks(chunk_prompts)

    def extract_bullet_points(generated_text):
        """
        Very simple parser that tries to remove leftover prompt
        and return only the bullet points.
        """

        marker = "BULLET POINT SUMMARY:"
        if marker in generated_text:

            _, _, remainder = generated_text.partition(marker)
            cleaned = remainder.strip()
            return cleaned
        else:

            return generated_text.strip()

    cleaned_chunk_summaries = [extract_bullet_points(text) for text in chunk_summaries_raw]

    summary_chunks = {
        docs[i].page_content: cleaned_chunk_summaries[i]
        for i in range(len(docs))
    }

    combined_summary = "\n".join(cleaned_chunk_summaries)

    final_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n"],
        chunk_size=5000,
        chunk_overlap=500
    )
    final_docs = final_splitter.create_documents([combined_summary])

    final_prompts = [
        f"""Summarize the following text in concise bullet points.
Return ONLY the bullet points without repeating the text:

TEXT:
{doc.page_content}

BULLET POINT SUMMARY:
"""
        for doc in final_docs
    ]

    final_summaries_raw = batch_summarize_chunks(final_prompts, max_new_tokens=200)
    final_summaries_clean = [extract_bullet_points(t) for t in final_summaries_raw]

    final_summary = "\n".join(final_summaries_clean).strip()

    summary_chunks = [
    f"Transcript: {transcript}\nSummary: {summary}"
    for transcript, summary in summary_chunks.items()
    ]

    return final_summary, summary_chunks