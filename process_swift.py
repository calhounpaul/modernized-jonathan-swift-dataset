import requests
from typing import List, Dict, Union, Optional
import json, hashlib, os, time

cache_dir = "completions_cache"
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

INITIAL_INSTRUCTION="""Please carefully consider how all the information in each piece of 18th century text can be fully translated into modern English. Do not change any details when modernizing. Do not alter names or terms. Do not remove or add information. Simply reshape the sentences one by one so they could be spoken by a modern person, while still referring to everything in the same way (e.g., for now-deceased public figures who were living when the quote was written, do not change the tense or any references).

OLD TEXT: {original}

Remember, when modernizing the sentences, ensure that you have not altered or removed any gender references. If a sentence starts with "Or," then the modernized version should also start with "Or," because you may not know what preceded it. The paragraphs below are grouped if they are consecutive. Just normalize the style without omitting any information. You should be able to convert each paragraph back and forth (i.e., from modernized to 18th-century language) without loss of meaning.

Start your response with "MODERNIZED TEXT:" followed by the modernized text. If you have any notes or questions, you can add a "NOTES:" section after the modernized text. The only thing between "MODERNIZED TEXT:" and "NOTES:" should be the modernized text itself. If you have no notes or questions, you can skip the "NOTES:" section."""

EXAMPLE_REPLY_FORMAT="""MODERNIZED TEXT: {modernized}"""

NEW_SECTION_INSTRUCTION="""This next paragraph is by the same author, but is not directly connected to the previous paragraph. Please modernize it independently (remember to only put comments in the "NOTES:" section if you have any):

OLD TEXT: {original}"""

SUBSEQUENT_PARAGRAPH_INSTRUCTION="""This next paragraph is by the same author, and directly follows the previous paragraph. Keep this in mind as you modernize it:

OLD TEXT: {original}"""

def get_next_chat_response(
    chat_history: List[Dict[str, str]],
    ip_address: str,
    model_name: str,
    stream: bool = False,
    options: Optional[Dict] = None,
    refresh_cache: bool = False,
) -> Dict:
    # Validate chat history format
    for message in chat_history:
        if not isinstance(message, dict):
            raise ValueError("Each message must be a dictionary")
        if 'role' not in message or 'content' not in message:
            raise ValueError("Each message must contain 'role' and 'content' keys")
        if message['role'] not in ['system', 'user', 'assistant', 'tool']:
            raise ValueError("Message role must be one of: system, user, assistant, or tool")
    last_message_content = chat_history[-1]["content"].split("TEXT:")[-1].strip()
    chat_history_hash = hashlib.md5(json.dumps(chat_history).encode()).hexdigest()
    cache_filename = "".join([c.lower() if c.isalnum() else "_" for c in last_message_content[:20]]) + f"_{chat_history_hash[-5:]}.json"
    cache_filepath = f"{cache_dir}/{cache_filename}"
    if not refresh_cache:
        try:
            with open(cache_filepath, "r") as file:
                response = json.load(file)["response"]
                print(f"Using cached response from {cache_filename}")
                response["cached"] = True
                return response
        except FileNotFoundError:
            pass
    # Construct the API endpoint URL
    api_url = f"http://{ip_address}:11434/api/chat"
    
    # Prepare the request payload
    payload = {
        "model": model_name,
        "messages": chat_history,
        "stream": stream
    }
    
    # Add options if provided
    if options:
        payload["options"] = options
        
    try:
        # Make the API call
        start_time = time.time()
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        time_delta = time.time() - start_time
        # Parse and return the response
        response = response.json()
        response["time_delta"] = time_delta
        with open(cache_filepath, "w") as file:
            json.dump({
                "request": payload,
                "response": response,
            }, file, indent=4)
        return response
        
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"API call failed: {str(e)}")

def normalize_swift_text(chat_response_kwargs={
        "ip_address": "127.0.0.1",
        "model_name":"nemotron:70b-instruct-q3_K_M",
        "options":{"temperature": 0.8,"num_ctx":8192},
    }):
    chat_history = []
    with open("examples_from_o1preview.json", "r") as file:
        sample_history = json.load(file)
    with open("jonathan_swift_contiguous_paragraphs.json", "r") as file:
        swift_paragraph_groups = json.load(file)
    STATIC_CHAT_HISTORY = []
    for subsequent_paragraph in sample_history[0:2]:
        #very first paragraph gets a special instruction
        if len(STATIC_CHAT_HISTORY) == 0:
            STATIC_CHAT_HISTORY.append({"role": "user", "content": INITIAL_INSTRUCTION.format(original=subsequent_paragraph[0]["original"])})
            STATIC_CHAT_HISTORY.append({"role": "assistant", "content": EXAMPLE_REPLY_FORMAT.format(modernized=subsequent_paragraph[0]["modernized"])})
            for subsequent_paragraph in subsequent_paragraph[1:]:
                STATIC_CHAT_HISTORY.append({"role": "user", "content": SUBSEQUENT_PARAGRAPH_INSTRUCTION.format(original=subsequent_paragraph["original"])})
                STATIC_CHAT_HISTORY.append({"role": "assistant", "content": EXAMPLE_REPLY_FORMAT.format(modernized=subsequent_paragraph["modernized"])})
        else:
            STATIC_CHAT_HISTORY.append({"role": "user", "content": NEW_SECTION_INSTRUCTION.format(original=subsequent_paragraph[0]["original"])})
            STATIC_CHAT_HISTORY.append({"role": "assistant", "content": EXAMPLE_REPLY_FORMAT.format(modernized=subsequent_paragraph[0]["modernized"])})
            for subsequent_paragraph in subsequent_paragraph[1:]:
                STATIC_CHAT_HISTORY.append({"role": "user", "content": SUBSEQUENT_PARAGRAPH_INSTRUCTION.format(original=subsequent_paragraph["original"])})
                STATIC_CHAT_HISTORY.append({"role": "assistant", "content": EXAMPLE_REPLY_FORMAT.format(modernized=subsequent_paragraph["modernized"])})
    
    generated_data = []
    groups_count = 0
    for swift_paragraph_group in swift_paragraph_groups:
        generated_group_data = []
        groups_count += 1
        dynamic_chat_history = []
        #first paragraph gets a special instruction
        dynamic_chat_history.append({"role": "user", "content": NEW_SECTION_INSTRUCTION.format(original=swift_paragraph_group[0])})
        #then get the modernized text for the first paragraph
        current_chat_history = STATIC_CHAT_HISTORY + dynamic_chat_history
        #print(current_chat_history)
        this_chat_response_kwargs = chat_response_kwargs.copy()
        this_chat_response_kwargs["chat_history"] = current_chat_history.copy()
        response = get_next_chat_response(**this_chat_response_kwargs)["message"]["content"]
        modernized_paragraph = response
        if "MODERNIZED TEXT:" in response:
            modernized_paragraph = response.split("MODERNIZED TEXT:")[-1].strip()
        notes = ""
        if "NOTES:" in response:
            notes = response.split("NOTES:")[-1].strip()
            modernized_paragraph = modernized_paragraph.split("NOTES:")[0].strip()
        generated_group_data.append({"original": swift_paragraph_group[0], "modernized": modernized_paragraph, "notes": notes})
        dynamic_chat_history.append({"role": "assistant", "content": response})
        print("ORIGINAL:",generated_group_data[-1]["original"],"\n")
        print("MODERNIZED:",generated_group_data[-1]["modernized"],"\n")
        print("NOTES:",generated_group_data[-1]["notes"])
        #then get the modernized text for the subsequent paragraphs
        print("GROUP:",groups_count,"/",len(swift_paragraph_groups))
        paragraphs_count = 1
        print("PARAGRAPH:",paragraphs_count,"/",len(swift_paragraph_group),"\n------------")
        for subsequent_paragraph in swift_paragraph_group[1:]:
            paragraphs_count += 1
            dynamic_chat_history.append({"role": "user", "content": SUBSEQUENT_PARAGRAPH_INSTRUCTION.format(original=subsequent_paragraph)})
            current_chat_history = STATIC_CHAT_HISTORY + dynamic_chat_history
            this_chat_response_kwargs = chat_response_kwargs.copy()
            this_chat_response_kwargs["chat_history"] = current_chat_history.copy()
            response = get_next_chat_response(**this_chat_response_kwargs)["message"]["content"]
            modernized_paragraph = response
            if "MODERNIZED TEXT:" in response:
                modernized_paragraph = response.split("MODERNIZED TEXT:")[-1].strip()
            notes = ""
            if "NOTES:" in response:
                notes = response.split("NOTES:")[-1].strip()
                modernized_paragraph = modernized_paragraph.split("NOTES:")[0].strip()
            generated_group_data.append({"original": subsequent_paragraph, "modernized": modernized_paragraph, "notes": notes})
            dynamic_chat_history.append({"role": "assistant", "content": response})
            print("ORIGINAL:",generated_group_data[-1]["original"],"\n")
            print("MODERNIZED:",generated_group_data[-1]["modernized"],"\n")
            print("NOTES:",generated_group_data[-1]["notes"])
            print("GROUP:",groups_count,"/",len(swift_paragraph_groups))
            print("PARAGRAPH:",paragraphs_count,"/",len(swift_paragraph_group),"\n------------")
        generated_data.append(generated_group_data)
        with open("modernized_jonathan_swift.json", "w") as file:
            json.dump(generated_data, file, indent=4)

def test_api():
    chat_history = [
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thank you! How can I help you today?"},
        {"role": "user", "content": "What is the capital of France?"}
    ]
    response = get_next_chat_response(
        chat_history=chat_history,
        ip_address="127.0.0.1",
        model_name="nemotron:70b-instruct-q3_K_M",
        options={"temperature": 0.8}
    )
    response = response["message"]["content"]
    print(response)


if __name__ == "__main__":
    #test_api()
    normalize_swift_text()