from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

model_id = "deepseek-ai/deepseek-llm-7b-chat"

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto",
    offload_folder="./offload"  # Make sure this folder exists
)

def generate_response(prompt):
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output = model.generate(
    **inputs,
    max_new_tokens=50,
    temperature=0.8,
    use_cache=False  # Helps reduce memory for long runs
)

    return tokenizer.decode(output[0], skip_special_tokens=True)

print(generate_response("Ask me a simple number puzzle. Don't give the answer."))

