import torch
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
import bitsandbytes as bnb  

model_name = "meta-llama/Llama-3.2-3B-Instruct"  

device_map = "auto" if torch.cuda.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(model_name)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    load_in_8bit=True,  
    device_map=device_map
)

chat_pipeline = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,  
    device_map=device_map
)

def chat_with_model(user_input, context=""):
    """
    Generate a response based on user input and optional context.
    """

    if context.strip():
        prompt = f"""[INST] 
        You are an assistant that answers questions based only on the provided knowledge. 
        You must not use any internal knowledge. When responding, do not mention that the answer is based on provided knowledge.

        The question: {user_input}

        The knowledge: {context} 
        [/INST]"""
    else:
        prompt = f"[INST] {user_input} [/INST]"

    output = chat_pipeline(
        prompt,
        max_new_tokens=128,
        eos_token_id=tokenizer.eos_token_id  
    )

    generated_text = output[0]["generated_text"]
    answer = generated_text.split("[/INST]")[-1].strip()

    return answer