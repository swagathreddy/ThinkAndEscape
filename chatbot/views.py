from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import logging
import uuid
import os

import traceback
import re
import requests
from PIL import Image
import io
import base64
import time
import unicodedata
from fuzzywuzzy import fuzz
from dotenv import load_dotenv


import json

# Add this function to help debug the issue
def debug_session(request, tag=""):
    """Print current session state for debugging"""
    theme = request.session.get("current_theme", "")
    element = request.session.get("current_element", "")
    last_image_theme = request.session.get("last_image_theme", "")
    
    print(f"[{tag}] SESSION STATE: Theme='{theme}', Element='{element}', LastImageTheme='{last_image_theme}'")

# Modified function for extracting themes and elements from response
def rotate_key():
    global current_key_index
    current_key_index = (current_key_index + 1) % len(OPEN_KEYS)
    print(f"[KEY ROTATED] Switched to key index {current_key_index}")
    return OPEN_KEYS[current_key_index]


def call_openrouter_api(messages, key):
    try:
        print(f"[DEBUG] Using OpenRouter API key: {key[:6]}...")
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek/deepseek-chat:free",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 600
        }
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"OpenRouter API error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print("Exception during OpenRouter call:", str(e))
        return None
        
def extract_candidates(text):
    """Extract numbered items from bot responses more reliably"""
    # Try standard pattern first
    candidates = re.findall(r'\d+\.\s+\*\*(.*?)\*\*', text)
    if not candidates:
        # Try alternative patterns that might appear in responses
        candidates = re.findall(r'\d+\.\s+(.*?)(?:\n|$)', text)
        if not candidates:
            candidates = re.findall(r'\d+\.\s+(.*?)\.', text)
    
    # Clean up any remaining formatting
    cleaned = []
    for c in candidates:
        c = c.strip()
        c = re.sub(r'\*\*', '', c)  # Remove any remaining ** marks
        c = re.sub(r'^[A-Z]\s+', '', c)  # Remove leading single letters like "A. "
        if c:
            cleaned.append(c)
    
    return cleaned


# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s: %(message)s',
    filename='django_errors.log'
)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

OPEN_KEYS = [k.strip() for k in os.getenv("OPEN_KEYS", "").split(",") if k.strip()]
if not OPEN_KEYS:
    logging.error("🚨 No OpenRouter API keys found in OPEN_KEYS.")
else:
    logging.warning(f"[DEBUG] OpenRouter Keys Loaded: {[k[:6] + '...' for k in OPEN_KEYS]}")


HF_KEYS = [k.strip() for k in os.getenv("HF_KEYS", "").split(",") if k.strip()]

# Track the current key index for key rotation
current_key_index = 0
MAX_RETRIES = 3





# Create initial client




@csrf_exempt
def index(request):
    request.session.flush()
    request.session.update({
        'game_session_id': str(uuid.uuid4()),
        'used_hint': False,
        'current_theme': "",
        'current_element': "",
        'last_themes': [],
        'last_elements': [],
        'chat_history': [],
        'solved_elements': [],
        'last_image_theme': "",
        'themes_shown': False  # New flag to track if themes were already shown
    })
    welcome_message = "Welcome to the Escape Room Game! 🏰 You will need to solve puzzles and riddles to progress through different rooms. Each room has its own challenge. Are you ready to begin your adventure? Type 'next' to continue."
    request.session["chat_history"] = [{"role": "assistant", "content": welcome_message}]
    return render(request, 'index.html', {'initial_puzzle': welcome_message})

@csrf_exempt
def fetch_elements(request):
    return JsonResponse({"elements": [
        "Control Panel", "Cryo Chamber", "Supply Locker", "Observation Deck", "Engineering Bay"
    ]})

def generate_theme_image(theme_name):
    """Generate an image for a theme using HuggingFace API or return fallback image"""
    print(f"[Image] Generating image for theme '{theme_name}'...")
    
    # Check if HF_KEYS is empty or contains invalid tokens
    if not HF_KEYS:
        print("[Image] No Hugging Face tokens available. Using fallback image.")
        return generate_fallback_image(theme_name)
    
    normalized_theme = unicodedata.normalize("NFKD", theme_name).encode("ascii", "ignore").decode("ascii")
    API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    
    working_token = False
    for token in HF_KEYS:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        prompt = f"A cinematic, atmospheric escape room in the theme of '{normalized_theme}'. Dramatic lighting, eerie or adventurous tone, high detail."
        
        try:
            print(f"[Image] Trying token: {token[:10]}...")
            response = requests.post(API_URL, headers=headers, json={
                "inputs": prompt,
                "parameters": {
                    "negative_prompt": "blurry, low quality, distorted, deformed",
                    "num_inference_steps": 30,
                    "guidance_scale": 7.5
                }
            }, timeout=30)
            
            if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
                working_token = True
                image = Image.open(io.BytesIO(response.content))
                # Resize to a consistent dimension that works well with the UI
                image.thumbnail((800, 500))
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                print(f"[Image] Successfully generated image for '{theme_name}'")
                return img_str
            
            elif response.status_code != 200:
                try:
                    error_json = response.json()
                    print(f"[Image] Token failed: {token[:10]} - {error_json.get('error', 'Unknown error')}")
                except:
                    print(f"[Image] Token failed: {token[:10]} - Status code: {response.status_code}")
        
        except Exception as e:
            print(f"[Image] Token failed: {token[:10]} - Exception: {str(e)}")
            time.sleep(1)
    
    print("[Image] All Hugging Face tokens failed. Using fallback image.")
    return generate_fallback_image(theme_name)

def generate_fallback_image(theme_name):
    """Generate a simple colored image with text as fallback"""
    try:
        # Create a more visually appealing fallback image
        width, height = 800, 500
        # Generate a consistent but varied color based on theme name
        import hashlib
        hash_object = hashlib.md5(theme_name.encode())
        hex_dig = hash_object.hexdigest()
        r = min(30 + int(hex_dig[0:2], 16) % 40, 255)  # Keep it dark-ish
        g = min(30 + int(hex_dig[2:4], 16) % 40, 255)
        b = min(60 + int(hex_dig[4:6], 16) % 60, 255)
        
        color = (r, g, b)  # Theme-based background color
        
        # Create a blank image with the specified color
        image = Image.new('RGB', (width, height), color)
        
        # Add a gradient effect (optional)
        for y in range(height):
            for x in range(width):
                # Add subtle gradient
                factor = 0.8 + (y / height) * 0.4
                current_color = (
                    int(min(r * factor, 255)),
                    int(min(g * factor, 255)),
                    int(min(b * factor, 255))
                )
                image.putpixel((x, y), current_color)
        
        # Save the image to a buffer
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        print(f"[Image] Created fallback image for '{theme_name}'")
        return img_str
    except Exception as e:
        print(f"[Image] Failed to create fallback image: {str(e)}")
        return None

@csrf_exempt
def chatbot_response(request):
    try:
        global client
        
        if request.method != 'POST':
            return JsonResponse({"error": "Invalid method"}, status=405)
    
        user_input = request.POST.get("user_input", "").strip()
        if not user_input:
            return JsonResponse({"error": "Empty input"}, status=400)
    
        # Debug current session state
        debug_session(request, "START")
    
        history = request.session.get("chat_history", [])
        used_hint = request.session.get("used_hint", False)
        solved_elements = request.session.get("solved_elements", [])
        age = request.session.get("player_age", None)
        themes_shown = request.session.get("themes_shown", False)
    
        if user_input.lower() == "next" and age is None:
            request.session["awaiting_age"] = True
            return JsonResponse({"response": "Before we begin, how old are you?"})
    
        if request.session.get("awaiting_age", False):
            if user_input.isdigit():
                request.session["player_age"] = int(user_input)
                request.session["awaiting_age"] = False
                return JsonResponse({"response": "Hi! Ready to start your escape room adventure? Would you like to pick a theme, or should I suggest some cool ones?"})
            else:
                return JsonResponse({"response": "Please enter your age as a number."})
    
        # Reset theme lists if the user asks for different themes
        if user_input.lower() in [
            "i want to select any other themes", "different theme", "change theme",
            "another theme", "new theme", "switch theme", "other theme", "other themes",
            "try a different theme", "next theme", "other room", "new room", "select another theme", 
            "show themes", "themes", "them", "theme", "suggest themes", "suggest"
        ] or "theme" in user_input.lower() and "other" in user_input.lower():
            print("[DEBUG] User requested a theme change or new themes")
            request.session["current_theme"] = ""
            request.session["current_element"] = ""
            request.session["last_image_theme"] = ""  
            request.session["themes_shown"] = False
            # Clear the last_themes to prevent selection conflicts
            request.session["last_themes"] = []
    
        # Parse the last bot message for themes or elements
        last_bot = history[-1]['content'] if history and history[-1]['role'] == 'assistant' else ""
        candidates = extract_candidates(last_bot)
        
        # Update themes/elements lists only when appropriate
        if candidates:
            # If the text has potential theme markers or the last message has numbered items with bold text
            if "**" in last_bot and (re.search(r'\d+\.\s+\*\*', last_bot) or "theme" in last_bot.lower()):
                print(f"[DEBUG] Found themes in last message: {candidates}")
                # Overwrite the previous themes with the new list
                request.session['last_themes'] = candidates
                print(f"[DEBUG] Updated themes list: {candidates}")
            elif request.session.get("current_theme") and not request.session.get("current_element"):
                print(f"[DEBUG] Found elements in last message: {candidates}")
                request.session['last_elements'] = candidates
    
        just_selected_theme = False
        just_selected_element = False
        image_data = None
    
        # Handle numeric input selection - check against current themes list
        if user_input.isdigit():
            idx = int(user_input) - 1
            themes = request.session.get("last_themes", [])
            
            if themes and 0 <= idx < len(themes):
                new_theme = themes[idx]
                print(f"[DEBUG] User selected theme #{idx+1}: '{new_theme}' from {themes}")
                request.session["current_theme"] = new_theme
                request.session["current_element"] = ""
                just_selected_theme = True
                
                # Generate image ONLY when theme is selected
                print(f"[DEBUG] Generating image for theme: {new_theme}")
                image_data = generate_theme_image(new_theme)
                print(f"[DEBUG] Image generation result: {'Success' if image_data else 'Failed'}")
                request.session["last_image_theme"] = new_theme
        
        # Handle text-based selection - themes or elements
        else:
            # Check if user is selecting a theme by name
            matched_theme = False
            for t in request.session.get("last_themes", []):
                if user_input.lower() in t.lower() or fuzz.partial_ratio(user_input.lower(), t.lower()) > 80:
                    print(f"[DEBUG] User selected theme by name: '{t}'")
                    request.session["current_theme"] = t
                    request.session["current_element"] = ""
                    just_selected_theme = True
                    matched_theme = True
                    
                    # Generate image ONLY when theme is selected
                    print(f"[DEBUG] Generating image for theme: {t}")
                    image_data = generate_theme_image(t)
                    print(f"[DEBUG] Image generation result: {'Success' if image_data else 'Failed'}")
                    request.session["last_image_theme"] = t
                    break
            
            # If not selecting theme, check if selecting element
            if not matched_theme:
                matched_element = False
                for e in request.session.get("last_elements", []):
                    if user_input.lower() in e.lower() or fuzz.partial_ratio(user_input.lower(), e.lower()) > 80:
                        print(f"[DEBUG] User selected element by name: '{e}'")
                        request.session["current_element"] = e
                        just_selected_element = True
                        matched_element = True
                        break
                
                # If still no match, try fuzzy matching for elements
                if not matched_element:
                    best_score = 0
                    best_match = None
                    for element in request.session.get("last_elements", []):
                        score = fuzz.partial_ratio(user_input.lower(), element.lower())
                        if score > best_score and score > 70:
                            best_match = element
                            best_score = score
                    if best_match:
                        print(f"[DEBUG] Fuzzy matched element: '{best_match}' (score: {best_score})")
                        request.session["current_element"] = best_match
                        just_selected_element = True
    
        # Handle "yes" as selection of first unsolved element
        if user_input.lower() in ["yes", "yeah", "yep", "sure"] and request.session.get("current_theme") and not request.session.get("current_element"):
            for e in request.session.get("last_elements", []):
                if e not in request.session.get("solved_elements", []):
                    print(f"[DEBUG] User said yes, selecting first unsolved element: '{e}'")
                    request.session["current_element"] = e
                    just_selected_element = True
                    break
    
        # Handle hint request
        if user_input.lower() in ["hint", "give me a hint", "i need a hint"] and request.session.get("current_element"):
            print("[DEBUG] User requested hint")
            request.session['used_hint'] = True
    
        theme = request.session.get("current_theme", "")
        element = request.session.get("current_element", "")
        difficulty = "easy" if age and age < 12 else "moderate" if age and age < 18 else "hard"
    
        # Update the system prompt to control the behavior
        system_prompt = f"""
        You are EscapeRoomBot, a friendly AI guide in a digital escape room game.
        The player is around {age if age else 'unknown'} years old.
        Based on this, use {difficulty} difficulty level when generating puzzles and themes.
    
        Your job is to walk the player through 3 simple phases:
        1. Theme Selection:
        - Ask if the user wants to pick a theme or see some cool ones.
        - If they ask for suggestions, give EXACTLY 5 short, creative themes with a ONE SENTENCE description.
        - Number themes from 1-5 and put theme names in bold (**Theme Name**).
        - IMPORTANT: DO NOT offer more themes after the user has made a selection.
        - User has {'' if themes_shown else 'not'} been shown themes yet.
    
        2. Element Selection:
        - Once a theme is selected, describe the room in 2-3 SHORT sentences.
        - List 3 relevant elements to explore, but DO NOT number them.
        - Instead, use bold formatting (**Element Name**) and tell the user to type the element name to interact with it.
        - Wait for the user to pick one by name.
    
        3. Puzzle Challenge:
        - Create a SHORT, {difficulty}-level puzzle involving the selected element.
        - Keep puzzles EXTREMELY SIMPLE with clear instructions.
        - For younger players (under 12), use mainly visual or counting puzzles.
        - For teens, use simple codes or logic puzzles.
        - For adults, use moderate difficulty puzzles.
        - Limit puzzle descriptions to 3-4 sentences maximum.wa
        - If the user asks for a hint, give ONE simple hint.
        - If their answer is correct, congratulate them briefly.
        - If wrong, tell them to try again or ask for a hint.
        - NEVER present choices with numbers (1, 2, 3) - require the user to type their answer.
        - This escape room is designed to make learning fun through gameplay. The puzzles and clues should always teach something meaningful related to the current theme — whether it's coding, history, science, math, art, or any other subject.
        - Make sure all challenges are technically or factually accurate and help reinforce real learning concepts.
        - Always stay focused on the theme the user selected, and avoid casual or unrelated responses.
    
    
    
        IMPORTANT GAME STATE:
        - Current theme: {theme}
        - Current element: {element}
        - Solved elements: {solved_elements}
        - Has themes been shown: {themes_shown}
    
        When the user selects a theme, immediately describe the room based on that theme and provide the 3 elements to interact with.
    
        DO NOT include score or lives in responses.
        KEEP ALL RESPONSES SHORT AND SIMPLE (maximum 4-5 sentences).
        DO NOT write long explanations.
        ALL RESPONSES MUST BE IN ENGLISH. No other languages should be used.
        """
    
        # Track if themes have been shown
        if "theme" in user_input.lower() or "suggest" in user_input.lower():
            request.session["themes_shown"] = True
        
        # Mark themes as shown when a theme is selected
        if just_selected_theme:
            request.session["themes_shown"] = True
            
        # Debug current state - helps diagnose issues
        print(f"[DEBUG] BEFORE API CALL - Theme: '{theme}', Element: '{element}', Just selected theme: {just_selected_theme}, Image data: {'Present' if image_data else 'None'}")
    
        messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_input}]
    
        # Try multiple keys if needed
        retries = 0
        while retries < MAX_RETRIES:
            try:
                key = OPEN_KEYS[current_key_index % len(OPEN_KEYS)]
                response_json = call_openrouter_api(messages, key)
                print("✅ OpenRouter response:", json.dumps(response_json, indent=2))

                if not response_json or "choices" not in response_json or not response_json["choices"]:
                    print("❌ OpenRouter returned no choices.")
                    if retries < MAX_RETRIES - 1:
                        current_key_index = (current_key_index + 1) % len(OPEN_KEYS)
                        retries += 1
                        time.sleep(1)
                        continue
                    break
                
                reply = response_json["choices"][0]["message"]["content"].strip()
    
                
                # Check for rate limit in error field
                
    
                # Add error handling for the message content
                choice = response_json["choices"][0]
                if "message" not in choice or "content" not in choice["message"]:
                    print("❌ Invalid message structure:", choice)
                    if retries < MAX_RETRIES - 1:
                        current_key_index = (current_key_index + 1) % len(OPEN_KEYS)
                        retries += 1
                        time.sleep(1)
                        continue
                    break


                    
                reply = choice["message"]["content"].strip()
                
                # Check for non-English content (add this to fix Chinese response issue)
                non_english_pattern = re.compile(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]')
                if non_english_pattern.search(reply):
                    print(f"❌ Detected non-English characters in response. Retrying...")
                    if retries < MAX_RETRIES - 1:
                        client = rotate_key()
                        retries += 1
                        time.sleep(1)
                        continue
                    # Fallback to English if all retries fail
                    reply = "I'm having trouble generating a proper response. Let's try again with a different approach. Would you like to see some theme options or continue with your current selection?"
    
                # Save themes as soon as they appear in the bot response
                # This ensures we catch any new theme lists right away
                if "1. **" in reply and "2. **" in reply:
                    new_candidates = extract_candidates(reply)
                    if new_candidates and len(new_candidates) >= 3:  # At least 3 items suggests a theme list
                        print(f"[DEBUG] Found new themes in response: {new_candidates}")
                        request.session['last_themes'] = new_candidates
                        print(f"[DEBUG] Updated themes list in response handler: {new_candidates}")
    
                # Check if the user's answer is correct
                if "correct" in reply.lower() and element:
                    element_key = element.lower()
                    if element_key not in solved_elements:
                        solved_elements.append(element_key)
                        request.session['solved_elements'] = solved_elements
                        request.session["current_element"] = ""
    
                # Remove any score or lives information from the response
                reply = re.sub(r'\ud83c\udf1f\s*Score:\s*\d+\s*\|\s*\u2764\ufe0f\s*Lives:\s*\d+', '', reply)
    
                # Remove numbered item lists in element descriptions
                if theme and not just_selected_theme and element:
                    # Replace numbered lists with plain text for puzzle options
                    reply = re.sub(r'\d+\.\s+(.*?)(?:\n|$)', r'\1\n', reply)
    
                # If this is a theme selection and the model is showing more themes (a common issue),
                # check and patch the response to prevent this behavior
                if just_selected_theme and re.search(r'\d+\.\s\*\*(.*?)\*\*', reply):
                    # Check if this is actually offering more themes rather than describing elements
                    if len(re.findall(r'\d+\.\s\*\*(.*?)\*\*', reply)) > 3:  # More than 3 numbered items suggests more themes
                        print("Detected potential theme list after theme selection, patching response...")
                        # Replace with a proper room description
                        fallback_elements = ["Control Console", "Hidden Compartment", "Strange Symbols"]
                        theme_desc = f"Great choice! You've selected **{theme}**.\n\n📜 **Room Description**: You find yourself in a themed escape room with various interactive elements. The atmosphere is tense and mysterious.\n\nHere are elements you can explore:\n\n**{fallback_elements[0]}**\n**{fallback_elements[1]}**\n**{fallback_elements[2]}**\n\nType the name of the element you'd like to investigate!"
                        reply = theme_desc
                        request.session["last_elements"] = fallback_elements
    
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": reply})
                request.session["chat_history"] = history
                request.session.modified = True
    
                # If image_data is True (flag), get the last image from session
               
    
                # Debug the image data
                print(f"[DEBUG] BEFORE RESPONSE - Sending response with image data: {'Present' if image_data else 'None'}")
                debug_session(request, "END")
                return JsonResponse({"response": reply, "image": image_data})
            
            except Exception as e:
                print(f"❌ OpenRouter error ({retries+1}/{MAX_RETRIES}):", traceback.format_exc())
                if retries < MAX_RETRIES - 1:
                    client = rotate_key()
                    retries += 1
                    time.sleep(1)  # Add a small delay between retries
                else:
                    break
    
        # Rest of the fallback code remains unchanged...
    
        # All retries failed or we encountered an unrecoverable error
        
        # Provide appropriate fallback responses
        if user_input.lower() in ["themes", "them", "theme", "themes", "suggest themes", "suggest", "show themes"]:
            fallback_response = "Here are some cool escape room themes to choose from:\n\n1. **Ancient Egyptian Tomb**\n2. **Space Station Meltdown**\n3. **Medieval Castle Dungeon**\n4. **Haunted Mansion**\n5. **Underwater Laboratory**\n\nType the number or name of the theme you'd like to explore!"
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": fallback_response})
            request.session["chat_history"] = history
            request.session["themes_shown"] = True
            request.session.modified = True
            return JsonResponse({"response": fallback_response, "image": None})
        
        # Fallback for element selection based on theme
        if theme and not element:
            theme_elements = {
                "Ancient Egyptian Tomb": ["Hieroglyphic Wall", "Pharaoh's Sarcophagus", "Hidden Chamber"],
                "Space Station Meltdown": ["Control Panel", "Airlock", "Reactor Core"],
                "Medieval Castle Dungeon": ["Rusty Cell Door", "Torch Sconce", "Mysterious Stones"],
                "Haunted Mansion": ["Dusty Portrait", "Music Box", "Creaking Bookshelf"],
                "Underwater Laboratory": ["Specimen Tank", "Control Console", "Diving Equipment"],
                # Add more themes including coding-related ones
                "The Debug Dungeon": ["Error Console", "Code Fragment", "Bug Jar"],
                "The Syntax Labyrinth": ["Parser Wall", "Function Gate", "Variable Chamber"],
                "The Algorithm Vault": ["Sorting Machine", "Binary Tree", "Complexity Analyzer"],
                "The Infinite Loop Maze": ["Counter Panel", "Exit Condition", "Iterator Device"],
                "The Binary Code Bunker": ["Binary Monitor", "Encryption Terminal", "Server Rack"],
                "The Byte-Sized Escape": ["Memory Array", "Logic Gate", "Compiler Station"],
                # Add Python-specific themes from the logs
                "Bugged Code Dungeon": ["Error Console", "Debug Terminal", "Logic Gate"],
                "AI Laboratory": ["Neural Network", "Training Data", "Model Parameters"],
                "Virtual Reality Glitch": ["Code Terminal", "VR Headset", "Simulation Controls"],
                "Data Heist": ["Security Terminal", "Data Vault", "Encryption Device"],
                "Python Pirate Ship": ["Navigation Console", "Code Treasure Chest", "Captain's Log"]
            }
            
            # Default elements if theme not found
            default_elements = ["Control Console", "Hidden Compartment", "Strange Symbols"]
            elements = theme_elements.get(theme, default_elements)
            
            fallback_response = f"Great choice! You've selected **{theme}**.\n\n📜 **Room Description**: You find yourself in a themed escape room with various interactive elements. The atmosphere is tense and mysterious.\n\nHere are elements you can explore:\n\n"
            fallback_response += "\n".join([f"**{element}**" for element in elements])
            fallback_response += "\n\nType the name of the element you'd like to investigate!"
            
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": fallback_response})
            request.session["chat_history"] = history
            request.session["last_elements"] = elements
            request.session.modified = True
            
            # Generate image for the theme if we're in the fallback case
            if not image_data and not request.session.get("last_image_theme"):
                print(f"[DEBUG] Generating fallback image for theme: {theme}")
                image_data = generate_theme_image(theme)
                print(f"[DEBUG] Image generation result: {'Success' if image_data else 'Failed'}")
                request.session["last_image_theme"] = theme
                
            return JsonResponse({"response": fallback_response, "image": image_data})
        
        # Generic fallback
        debug_session(request, "ERROR")
        return JsonResponse({"error": True, "response": "⚠️ Our AI assistant is temporarily unavailable. Please try again in a moment."}, status=500)
    except Exception as e:
        print("[FATAL ERROR] chatbot_response failed:", traceback.format_exc())
        debug_session(request, "FATAL")
        return JsonResponse({
            "error": True,
            "response": "⚠️ Internal server error. Please try again later."
        }, status=500)

        

   

