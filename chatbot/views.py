from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .logic import PuzzleLogic
from .models import Element
import logging
import uuid
import os
from openai import OpenAI
import traceback
import re
import requests
from PIL import Image
import io
import base64
import time

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s: %(message)s',
    filename='django_errors.log'
)

# Setup DeepSeek client (via OpenRouter)
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY", "your-default-key-here"),
    base_url="https://openrouter.ai/api/v1"
)

class EscapeRoomView:
    def __init__(self, session=None):
        self.puzzle_logic = PuzzleLogic()
        self.hf_api_token = os.getenv("HF_API_KEY")
        if session:
            if 'game_session_id' not in session:
                session['game_session_id'] = str(uuid.uuid4())
            self.puzzle_logic.set_session(session['game_session_id'])
            state = session.get('puzzle_logic_state', None)
            if state:
                self.puzzle_logic.from_dict(state)

    def save_session(self, session):
        session['puzzle_logic_state'] = self.puzzle_logic.to_dict()
        session.modified = True

    def get_initial_puzzle(self):
        return self.puzzle_logic.start_game() if not self.puzzle_logic.game_started else self.puzzle_logic.get_puzzle()

    def generate_element_image(self, subject_name, theme_context):
        print(f"[Image] Calling Hugging Face with prompt for '{subject_name}' in theme '{theme_context}'...")
        API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        print("HF API Key Present:", bool(self.hf_api_token))

        headers = {
            "Authorization": f"Bearer {self.hf_api_token}",
            "Content-Type": "application/json"
        }
        prompt = f"Illustration of '{subject_name}' in the theme of '{theme_context}'. Stylized, atmospheric, cinematic lighting."
        for attempt in range(3):
            try:
                response = requests.post(API_URL, headers=headers, json={
                    "inputs": prompt,
                    "parameters": {
                        "negative_prompt": "blurry, low quality, bad composition",
                        "num_inference_steps": 30,
                        "guidance_scale": 7.5
                    }
                }, timeout=30)

                print(f"[Image] Response Status: {response.status_code}")
                content_type = response.headers.get("Content-Type", "")

                if response.status_code == 200:
                    if "image" in content_type:
                        image = Image.open(io.BytesIO(response.content))
                        image.thumbnail((400, 400))
                        buffered = io.BytesIO()
                        image.save(buffered, format="PNG")
                        base64_img = base64.b64encode(buffered.getvalue()).decode('utf-8')
                        print("[Image] Successfully generated base64 image")
                        return base64_img

                    elif "json" in content_type:
                        json_data = response.json()
                        print("[Image] JSON response from Hugging Face:", json_data)
                        base64_image = json_data.get("generated_image") or json_data.get("image")
                        if base64_image:
                            print("[Image] Base64 string extracted from JSON")
                            return base64_image

                else:
                    print("[Image] Non-200 response:", response.text[:200])

            except Exception as e:
                print("[Image] Exception during image generation:", e)
                logging.error(f"Image generation exception: {e}")
                time.sleep(1)

        print("[Image] Failed to generate image after retries")
        return None


@csrf_exempt
def index(request):
    request.session.flush()
    request.session.update({
        'game_session_id': str(uuid.uuid4()),
        'score': 0,
        'used_hint': False,
        'current_theme': "",
        'current_element': "",
        'last_themes': [],
        'last_elements': [],
        'chat_history': [],
        'solved_elements': []
    })
    view = EscapeRoomView(request.session)
    return render(request, 'index.html', {'initial_puzzle': view.get_initial_puzzle()})


@csrf_exempt
def fetch_elements(request):
    return JsonResponse({"elements": [
        "Control Panel",
        "Cryo Chamber",
        "Supply Locker",
        "Observation Deck",
        "Engineering Bay"
    ]})


@csrf_exempt
def chatbot_response(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid method"}, status=405)

    user_input = request.POST.get("user_input", "").strip()
    if not user_input:
        return JsonResponse({"error": "Empty input"}, status=400)

    history = request.session.get("chat_history", [])
    score = request.session.get("score", 0)
    used_hint = request.session.get("used_hint", False)
    solved_elements = request.session.get("solved_elements", [])
    just_asked_hint = user_input.lower() in ["hint", "give me a hint", "i need a hint"]
    if just_asked_hint:
        request.session['used_hint'] = True

    last_bot = history[-1]['content'] if history and history[-1]['role'] == 'assistant' else ""
    candidates = re.findall(r'\d+\.\s\*\*(.*?)\*\*', last_bot)
    if candidates:
        if not request.session.get("current_theme"):
            print("📌 Extracted new themes:", candidates)
            request.session['last_themes'] = candidates
            request.session['current_theme'] = ""
        else:
            print("📌 Extracted new elements:", candidates)
            request.session['last_elements'] = candidates
            request.session['current_element'] = ""

    just_selected_element = False
    just_selected_theme = False

    if user_input.isdigit():
        idx = int(user_input) - 1
        if not request.session.get("current_theme"):
            themes = request.session.get("last_themes", [])
            if 0 <= idx < len(themes):
                request.session["current_theme"] = themes[idx]
                just_selected_theme = True
        else:
            elements = request.session.get("last_elements", [])
            if 0 <= idx < len(elements):
                request.session["current_element"] = elements[idx]
                just_selected_element = True
    else:
        if not request.session.get("current_theme"):
            themes = request.session.get("last_themes", [])
            for t in themes:
                if user_input.lower() in t.lower():
                    request.session["current_theme"] = t
                    just_selected_theme = True
                    break
        else:
            elements = request.session.get("last_elements", [])
            for e in elements:
                if user_input.lower() in e.lower():
                    request.session["current_element"] = e
                    just_selected_element = True
                    break
        if user_input.lower() in ["yes", "yeah", "yep"] and not request.session.get("current_element"):
            last_elements = request.session.get("last_elements", [])
            if last_elements:
                for e in last_elements:
                    if e not in request.session.get("solved_elements", []):
                        request.session["current_element"] = e
                        just_selected_element = True
                        print("✅ Auto-selected element for 'yes':", e)
                        break

    theme = request.session.get("current_theme", "")
    element = request.session.get("current_element", "")
    print(f"🎯 Current Theme: '{theme}', Current Element: '{element}'")

    system_prompt = f"""
You are EscapeRoomBot, a friendly AI guide in a digital escape room game.
The player is interested in topics like: {theme if theme else 'Not specified yet'}.

Your job is to walk the player through 3 simple phases:
1. Theme Selection:
   - Ask if the user wants to pick a theme or see some cool ones.
   - If they ask for suggestions, give 5 short, creative themes related to their interest.
   - Wait for the user to choose one.
2. Element Selection:
   - Based on the theme, describe the room briefly.
   - List 3 relevant elements to explore.
   - Wait for the user to pick one.
3. Puzzle Challenge:
   - Create a short, theme-based puzzle involving the selected element.
   - If the user asks for a hint, give one. 
   - If their answer is correct, award points: +10 (no hint), +5 (with hint).
   - If wrong, say it's incorrect and suggest trying again or using a hint.

Keep your replies short, clear, and easy to understand.
Don't explain your reasoning or describe what's happening behind the scenes.
Theme: {theme or "Not selected"}
Element: {element or "Not selected"}
Last Reply: {last_bot}
"""

    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_input}]

    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-chat:free",
            messages=messages,
            temperature=0.8,
            max_tokens=400
        )

        if not response or not response.choices or not response.choices[0].message:
            raise ValueError("Invalid response from OpenRouter (missing choices or message)")

        reply = response.choices[0].message.content.strip()
        print("🧠 Full bot reply:", reply)

        view = EscapeRoomView(request.session)
        image_data = None

        # ✅ Only generate images for newly selected themes or elements
        if just_selected_theme:
            print(f"🖼️ Generating image for selected theme: {theme}")
            image_data = view.generate_element_image(subject_name=theme, theme_context=theme)

        elif just_selected_element:
            print(f"📸 Generating image for active element: {element}")
            image_data = view.generate_element_image(subject_name=element, theme_context=theme)

        else:
            print("⛔ Skipping image generation – no new element or theme detected.")

        if "correct" in reply.lower() and element:
            if element not in solved_elements:
                score += 5 if used_hint else 10
                solved_elements.append(element)
                request.session['solved_elements'] = solved_elements
                request.session['used_hint'] = False
            else:
                print("⚠️ Already solved this element. Skipping score update.")
        elif just_asked_hint:
            request.session['used_hint'] = True
        else:
            request.session['used_hint'] = False

        history.append({"role": "assistant", "content": reply})
        request.session.update({
            "chat_history": history,
            "score": score
        })
        request.session.modified = True

        return JsonResponse({"response": reply, "score": score, "image": image_data})

    except Exception as e:
        print("❌ OpenRouter error:", traceback.format_exc())
        return JsonResponse({
            "error": True,
            "response": "⚠️ DeepSeek is not responding. Please check your connection or try again later."
        }, status=500)
