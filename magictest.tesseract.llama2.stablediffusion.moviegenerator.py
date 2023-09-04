from typing import List
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from moviepy.editor import ImageSequenceClip
from PIL import Image
import pytesseract
import asyncio
import random
import requests
import sys
import io
import base64
import os
import re
import hashlib
from concurrent.futures import ThreadPoolExecutor

# Assuming you have the Llama2 Python bindings
from llama_cpp import Llama

# Initialize FastAPI
app = FastAPI()

# Initialize ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=1)

# Initialize Llama2
script_dir = os.path.dirname(os.path.realpath(__file__))
model_path = os.path.join(script_dir, "llama-2-7b-chat.ggmlv3.q8_0.bin")
llm = Llama(model_path=model_path, n_ctx=3999)

# Function to extract seed from story
def extract_seed_from_story(story):
    match = re.search(r'New Seed: (\d+)', story)
    if match:
        return int(match.group(1))
    return None

def generate_dynamic_seed(story, feedback):
    emotion_factor = 0
    tone_factor = 0
    change_factor = 0
    emotions = {"happy": 1, "sad": 2, "angry": 3, "excited": 4, "nervous": 5, "relaxed": 6}
    tones = {"serious": 1, "casual": 2, "urgent": 3, "calm": 4}
    for emotion, factor in emotions.items():
        if emotion in story.lower():
            emotion_factor = factor
    for tone, factor in tones.items():
        if tone in story.lower():
            tone_factor = factor
    if "change" in feedback.lower():
        change_factor = 1
    seed_string = f"{emotion_factor}{tone_factor}{change_factor}"
    seed_hash = hashlib.md5(seed_string.encode()).hexdigest()
    seed = int(seed_hash, 16) % sys.maxsize
    if emotion_factor == 0 and tone_factor == 0 and change_factor == 0:
        return None
    return seed

async def llama_generate_async(prompt):
    loop = asyncio.get_event_loop()
    output = await loop.run_in_executor(executor, lambda: llm(prompt, max_tokens=3999))
    return output

async def generate_images(prompt: str, prev_seed: int) -> List[Image.Image]:
    print("starting generation service")
    images = []
    seed = prev_seed if prev_seed else random.randrange(sys.maxsize)
    url = 'http://127.0.0.1:7860/sdapi/v1/txt2img'
    payload = {
        "prompt": prompt,
        "steps": 9,
        "seed": seed,
        "enable_hr": "false",
        "denoising_strength": "0.7",
        "cfg_scale": "7",
        "width": 1000,
        "height": 427,
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        try:
            r = response.json()
            # print(r)
            for i in r['images']:
                images.append(Image.open(io.BytesIO(base64.b64decode(i))))
        except ValueError as e:
            print("Error processing image data: ", e)
    else:
        print("Error generating image: ", response.status_code)
    print("completed images")
    return images, seed

@app.get("/generate_movie/{topic}")
async def generate_movie(topic: str):
    storyline = ""
    images = []
    total_frames = 50  # 24 FPS * 60 seconds * 5 minutes
    prev_seed = None  # Initialize with None

    for frame in range(total_frames):
        prompt = f"1. Current Topic: {topic}\n2. Frame Number: {frame}\n3. Existing Storyline: {storyline}\n4. Current Seed: {prev_seed}\n5. Objective: Generate the next part of the storyline for frame {frame} and suggest a new seed if necessary.\nWhat happens next?"
        segment_story = await llama_generate_async(prompt)
        
        # Extract the text from the Llama model's output and append it to the storyline
        storyline += segment_story['choices'][0]['text']

        new_seed_suggested = extract_seed_from_story(segment_story['choices'][0]['text'])

        image_prompt = f"1. Current Topic: {topic}\n2. Frame Number: {frame}\n3. Generated Story: {segment_story}\n4. Current Seed: {prev_seed}\n5. Objective: Generate an image that aligns with the story.\nCreate Image."
        segment_images, new_seed = await generate_images(image_prompt, prev_seed)
        images.extend(segment_images)

        text = pytesseract.image_to_string(segment_images[0])

        feedback_prompt = f"1. Current Topic: {topic}\n2. Frame Number: {frame}\n3. OCR Reading: {text}\n4. Objective: Validate if the movie is going in the right direction based on the OCR reading.\nIs it aligned?"
        feedback = await llama_generate_async(feedback_prompt)

        if "change" in feedback.lower():
            storyline += f"\n[Director's note for frame {frame}: Adjusting direction based on feedback.]"

        dynamic_seed = generate_dynamic_seed(segment_story, feedback)
        prev_seed = dynamic_seed if dynamic_seed else new_seed_suggested if new_seed_suggested else new_seed

# Add these lines to run your FastAPI app with Uvicorn (not Waitress)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
